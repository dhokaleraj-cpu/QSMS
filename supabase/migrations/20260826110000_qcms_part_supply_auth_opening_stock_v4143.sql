begin;

-- QCMS v4.14.3
-- Additive Part Master / Supply Chain / OSP / access improvements.
-- No existing transactional or master rows are deleted.

-- 1) Multiple material grades per Part while retaining parts.material_grade_id as Primary Grade.
create table if not exists public.part_material_grade_links(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  part_id uuid not null references public.parts(id) on delete cascade,
  material_grade_id uuid not null references public.material_grades(id) on delete restrict,
  is_primary boolean not null default false,
  status text not null default 'ACTIVE' check(status in ('ACTIVE','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(tenant_id,part_id,material_grade_id)
);
create unique index if not exists uq_qcms_part_primary_material_grade
  on public.part_material_grade_links(tenant_id,part_id) where is_primary=true and status='ACTIVE';
create index if not exists idx_qcms_part_material_grade_lookup
  on public.part_material_grade_links(tenant_id,part_id,status,material_grade_id);

insert into public.part_material_grade_links(tenant_id,part_id,material_grade_id,is_primary,status)
select p.tenant_id,p.id,p.material_grade_id,true,'ACTIVE'
from public.parts p
where p.material_grade_id is not null
on conflict(tenant_id,part_id,material_grade_id) do update
set is_primary=excluded.is_primary,status='ACTIVE',updated_at=now();

-- Each supplier / RM section may have its own approved grade and lead time.
alter table public.part_raw_material_details
  add column if not exists material_grade_id uuid references public.material_grades(id) on delete restrict,
  add column if not exists lead_time_days integer not null default 0;

do $$ begin
  alter table public.part_raw_material_details add constraint ck_qcms_rm_lead_time_nonnegative check(lead_time_days>=0);
exception when duplicate_object then null; end $$;

update public.part_raw_material_details r
set material_grade_id=p.material_grade_id
from public.parts p
where p.id=r.part_id and r.material_grade_id is null and p.material_grade_id is not null;

comment on column public.part_raw_material_details.material_grade_id is
  'QCMS v4.14.3 approved grade for this supplier/raw-material section. Multiple grades and sections are allowed per Part.';
comment on column public.part_raw_material_details.lead_time_days is
  'QCMS v4.14.3 supplier/raw-material lead time used to default PO delivery date; PO user can override the calculated date.';

-- Earlier QCMS versions permitted only one raw-material row per Part/Supplier.
-- v4.14.3 deliberately removes that uniqueness because a supplier may supply
-- multiple grades and/or raw-material sections for the same Part.
alter table public.part_raw_material_details
  drop constraint if exists part_raw_material_details_tenant_id_part_id_supplier_id_key;
drop index if exists public.part_raw_material_details_tenant_id_part_id_supplier_id_key;
create index if not exists idx_qcms_part_raw_material_supplier_grade_section
  on public.part_raw_material_details(tenant_id,part_id,supplier_id,material_grade_id,material_section_name,status);

-- 2) Opening stock by Part and current Supply Chain stage.
create table if not exists public.supply_opening_stock(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  part_id uuid not null references public.parts(id) on delete restrict,
  stage text not null check(stage in ('RAW_MATERIAL','FORGING','MACHINING','OSP_READY','AT_OSP','FINAL_INSPECTION','FINISHED_GOODS')),
  material_grade_id uuid references public.material_grades(id) on delete set null,
  raw_material_detail_id uuid references public.part_raw_material_details(id) on delete set null,
  supplier_id uuid references public.parties(id) on delete set null,
  lot_reference text,
  heat_number text,
  heat_code text,
  quantity_pcs numeric not null default 0 check(quantity_pcs>=0),
  available_quantity_pcs numeric not null default 0 check(available_quantity_pcs>=0),
  quantity_kg numeric not null default 0 check(quantity_kg>=0),
  remarks text,
  status text not null default 'ACTIVE' check(status in ('ACTIVE','CONSUMED','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);
create index if not exists idx_qcms_opening_stock_part_stage
  on public.supply_opening_stock(tenant_id,part_id,stage,status,available_quantity_pcs);

-- Opening stock can become a genuine OSP source without inventing an RMTC/Inward.
alter table public.production_batches alter column inward_lot_id drop not null;
alter table public.production_batches
  add column if not exists opening_stock_id uuid references public.supply_opening_stock(id) on delete restrict;
alter table public.osp_jobs
  add column if not exists opening_stock_id uuid references public.supply_opening_stock(id) on delete restrict;
create index if not exists idx_qcms_production_batch_opening_stock on public.production_batches(opening_stock_id);
create index if not exists idx_qcms_osp_opening_stock on public.osp_jobs(opening_stock_id);

-- 3) Password-controlled edit audit. This does not grant permission by itself;
-- the user must also have Edit permission for the relevant QCMS module.
create table if not exists public.qcms_password_edit_audit(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  action text not null default 'PASSWORD_EDIT_UNLOCK',
  reason text,
  status_before text,
  disposition_before text,
  edited_by uuid not null default auth.uid(),
  created_at timestamptz not null default now()
);
create index if not exists idx_qcms_password_edit_audit_entity
  on public.qcms_password_edit_audit(tenant_id,entity_type,entity_id,created_at desc);

-- Profiles may now use functional business roles in addition to legacy quality roles.
alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles add constraint profiles_role_check check(role in (
  'ADMIN','MANAGEMENT','SUPPLY_CHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT',
  'QUALITY_MANAGER','METLAB_APPROVER','QUALITY_ENGINEER','PRODUCTION','SQA','MASTER_DATA','AUDITOR','VIEWER'
));

-- 4) New functional-role / department aware table-to-module mapping.
create or replace function public.qsms_module_for_table(target_table text) returns text
language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_material_grade_links','part_raw_material_details','part_raw_material_technical_data','part_supplier_price_history','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments','part_standard_links') then 'PART_MASTER'
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
 when target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then 'COMPLAINT_MANAGEMENT'
 when target_table in ('supply_customer_orders','supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then 'SUPPLY_CHAIN'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare
 role_name text:=coalesce(public.current_app_role(),'VIEWER');
 department_name text;
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 select upper(regexp_replace(coalesce(e.department,''),'[^A-Za-z0-9]+','_','g'))
 into department_name
 from public.employees e
 where e.tenant_id=public.current_tenant_id() and e.profile_id=auth.uid() and e.status='ACTIVE'
 order by e.updated_at desc limit 1;

 if target_table in ('parties','material_grades','material_grade_elements','parts','part_material_grade_links','part_supplier_links','part_raw_material_details','part_raw_material_technical_data','part_supplier_price_history','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links','processes','inspection_stages','master_value_catalog','customer_standards') then
   return role_name in ('QUALITY_MANAGER','MASTER_DATA','PROCUREMENT','MANAGEMENT');
 elsif target_table in ('employees','quality_assets') then
   return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER','MANAGEMENT');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then
   return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA','MANAGEMENT');
 elsif target_table='inward_lots' then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','SUPPLY_CHAIN','PROCUREMENT','MANAGEMENT') or department_name in ('SUPPLY_CHAIN','SUPPLYCHAIN','PROCUREMENT','MANAGEMENT');
 elsif target_table in ('production_batches','batch_movements','osp_jobs') then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','SUPPLY_CHAIN','MANAGEMENT') or department_name in ('SUPPLY_CHAIN','SUPPLYCHAIN','MANAGEMENT');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','MANAGEMENT');
 elsif target_table in ('inspection_reports','inspection_results') then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','MANAGEMENT');
 elsif target_table='lab_tests' then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','MANAGEMENT');
 elsif target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION','BUSINESS_DEVELOPMENT','MANAGEMENT');
 elsif target_table='qc_calculation_records' then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','MANAGEMENT');
 elsif target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','BUSINESS_DEVELOPMENT','MANAGEMENT');
 elsif target_table in ('supply_customer_orders','supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then
   return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION','SUPPLY_CHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT','MANAGEMENT')
      or department_name in ('SUPPLY_CHAIN','SUPPLYCHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT','MANAGEMENT');
 end if;
 return false;
end;
$$;

-- Customer Order attachments use the same controlled attachment service and Storage bucket.
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
 else null end;
$$;

create or replace function public.qsms_can_manage_attachment(p_entity_type text,p_action text default 'EDIT') returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare
 v_role text:=coalesce(public.current_app_role(),'VIEWER');
 v_module text:=public.qsms_attachment_module(p_entity_type);
 v_action text:=upper(coalesce(p_action,'EDIT'));
 v_department text;
begin
 if auth.uid() is null or public.current_tenant_id() is null then return false; end if;
 if v_role='ADMIN' then return true; end if;
 if v_module is null then return false; end if;
 if exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=v_module and p.can_view and case when v_action='CREATE' then p.can_create when v_action='ARCHIVE' then p.can_archive else p.can_edit end) then return true; end if;
 select upper(regexp_replace(coalesce(e.department,''),'[^A-Za-z0-9]+','_','g')) into v_department
 from public.employees e where e.tenant_id=public.current_tenant_id() and e.profile_id=auth.uid() and e.status='ACTIVE' order by e.updated_at desc limit 1;
 return case v_module
  when 'PART_MASTER' then v_role in ('QUALITY_MANAGER','MASTER_DATA','PROCUREMENT','MANAGEMENT')
  when 'RMTC_ENTRY' then v_role in ('QUALITY_MANAGER','METLAB_APPROVER','SQA','MANAGEMENT')
  when 'MATERIAL_INWARD' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','SUPPLY_CHAIN','PROCUREMENT','MANAGEMENT')
  when 'DIMENSIONAL_REPORT' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','MANAGEMENT')
  when 'METLAB_REPORT' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','MANAGEMENT')
  when 'COMPLAINT_MANAGEMENT' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','BUSINESS_DEVELOPMENT','MANAGEMENT')
  when 'SUPPLY_CHAIN' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION','SUPPLY_CHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT','MANAGEMENT') or v_department in ('SUPPLY_CHAIN','SUPPLYCHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT','MANAGEMENT')
  else false end;
end;
$$;

-- 5) RLS / audit for the new tables.
do $$
declare table_name text;
begin
 foreach table_name in array array['part_material_grade_links','supply_opening_stock','qcms_password_edit_audit'] loop
  execute format('alter table public.%I enable row level security',table_name);
  execute format('drop policy if exists tenant_select on public.%I',table_name);
  execute format('drop policy if exists tenant_insert on public.%I',table_name);
  execute format('drop policy if exists tenant_update on public.%I',table_name);
  execute format('drop policy if exists tenant_delete on public.%I',table_name);
  execute format('create policy tenant_select on public.%I for select to authenticated using(tenant_id=public.current_tenant_id())',table_name);
 end loop;
end $$;

create policy tenant_insert on public.part_material_grade_links for insert to authenticated
with check(tenant_id=public.current_tenant_id() and public.can_write_table('parts'));
create policy tenant_update on public.part_material_grade_links for update to authenticated
using(tenant_id=public.current_tenant_id() and public.can_write_table('parts'))
with check(tenant_id=public.current_tenant_id() and public.can_write_table('parts'));
create policy tenant_delete on public.part_material_grade_links for delete to authenticated
using(tenant_id=public.current_tenant_id() and public.can_write_table('parts'));

create policy tenant_insert on public.supply_opening_stock for insert to authenticated
with check(tenant_id=public.current_tenant_id() and public.can_write_table('supply_opening_stock'));
create policy tenant_update on public.supply_opening_stock for update to authenticated
using(tenant_id=public.current_tenant_id() and public.can_write_table('supply_opening_stock'))
with check(tenant_id=public.current_tenant_id() and public.can_write_table('supply_opening_stock'));
create policy tenant_delete on public.supply_opening_stock for delete to authenticated
using(tenant_id=public.current_tenant_id() and public.can_write_table('supply_opening_stock'));

create policy tenant_insert on public.qcms_password_edit_audit for insert to authenticated
with check(tenant_id=public.current_tenant_id() and edited_by=auth.uid());
-- Audit rows are immutable to application users.

-- Standard update/audit triggers where columns exist.
drop trigger if exists trg_touch_updated_at on public.part_material_grade_links;
create trigger trg_touch_updated_at before update on public.part_material_grade_links for each row execute function public.touch_updated_at();
drop trigger if exists trg_audit_row_change on public.part_material_grade_links;
create trigger trg_audit_row_change after insert or update or delete on public.part_material_grade_links for each row execute function public.log_row_change();
drop trigger if exists trg_touch_updated_at on public.supply_opening_stock;
create trigger trg_touch_updated_at before update on public.supply_opening_stock for each row execute function public.touch_updated_at();
drop trigger if exists trg_audit_row_change on public.supply_opening_stock;
create trigger trg_audit_row_change after insert or update or delete on public.supply_opening_stock for each row execute function public.log_row_change();

grant select,insert,update,delete on public.part_material_grade_links to authenticated;
grant select,insert,update,delete on public.supply_opening_stock to authenticated;
grant select,insert on public.qcms_password_edit_audit to authenticated;

-- 6) OSP register supports either a normal Inward source or Opening Stock source.
create or replace view public.v_qsms_osp_register with (security_invoker=true) as
select
 o.id,o.tenant_id,o.osp_job_number,o.source_batch_id,o.osp_batch_id,o.part_id,o.vendor_id,o.process_id,
 o.dispatch_date,o.dispatch_challan,o.quantity_dispatched,o.expected_return_date,o.process_specification,o.required_tests,
 o.receipt_date,o.receipt_challan,o.vendor_batch_number,o.quantity_received,o.quantity_rejected_at_receipt,o.receipt_status,
 o.inspection_status,o.status,o.receipt_remarks,o.created_at,o.updated_at,o.created_by,o.updated_by,
 o.source_inward_lot_id,o.process_specification_id,o.inward_type,o.sample_quantity,o.sample_received_date,o.sample_reference,
 o.sample_gate_status,o.full_receipt_authorized_at,o.full_receipt_authorized_by,o.receipt_number,o.vendor_invoice_number,
 o.vendor_invoice_date,o.tc_number,o.tc_date,o.receipt_quality_disposition,o.production_released_at,o.dispatch_remarks,
 source_batch.heat_number,source_batch.heat_code,source_batch.batch_code as source_batch_code,
 osp_batch.batch_code as osp_batch_code,osp_batch.quantity_available as production_available_quantity,
 coalesce(i.inward_number, os.lot_reference, 'OPENING STOCK') as inward_number,
 coalesce(i.inward_date, os.created_at::date) as inward_date,
 coalesce(i.quality_disposition, 'OPENING_STOCK') as source_quality_disposition,
 p.part_number,p.part_name,vendor.party_code as vendor_code,vendor.party_name as vendor_name,
 process.process_code,process.process_name,process.process_type,
 specification.inward_type as specification_inward_type,specification.dimensional_required,specification.metlab_required,
 coalesce((select r.disposition from public.inspection_reports r where r.osp_job_id=o.id and r.report_type='DIMENSIONAL' and r.inspection_scope='OSP_SAMPLE' order by r.decision_at desc nulls last,r.updated_at desc limit 1),'PENDING') as sample_dimensional_disposition,
 coalesce((select l.disposition from public.lab_tests l where l.osp_job_id=o.id and l.test_type='METLAB' and l.inspection_scope='OSP_SAMPLE' order by l.decision_at desc nulls last,l.updated_at desc limit 1),'PENDING') as sample_metlab_disposition,
 coalesce((select r.disposition from public.inspection_reports r where r.osp_job_id=o.id and r.report_type='DIMENSIONAL' and r.inspection_scope='OSP_RECEIPT' order by r.decision_at desc nulls last,r.updated_at desc limit 1),'PENDING') as receipt_dimensional_disposition,
 coalesce((select l.disposition from public.lab_tests l where l.osp_job_id=o.id and l.test_type='METLAB' and l.inspection_scope='OSP_RECEIPT' order by l.decision_at desc nulls last,l.updated_at desc limit 1),'PENDING') as receipt_metlab_disposition,
 o.sample_gate_status in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') as full_receipt_allowed,
 greatest(o.quantity_dispatched-o.quantity_received,0) as quantity_outstanding,
 o.opening_stock_id
from public.osp_jobs o
join public.production_batches source_batch on source_batch.id=o.source_batch_id
join public.production_batches osp_batch on osp_batch.id=o.osp_batch_id
left join public.inward_lots i on i.id=o.source_inward_lot_id
left join public.supply_opening_stock os on os.id=o.opening_stock_id
join public.parts p on p.id=o.part_id
join public.parties vendor on vendor.id=o.vendor_id
join public.processes process on process.id=o.process_id
left join public.part_process_specifications specification on specification.id=o.process_specification_id;

grant select on public.v_qsms_osp_register to authenticated;

-- 7) Genuine OSP dispatch from opening stock.
create or replace function public.qsms_create_osp_dispatch_from_opening_stock(
 p_opening_stock_id uuid,p_vendor_id uuid,p_process_id uuid,p_process_specification_id uuid,
 p_dispatch_date date,p_dispatch_challan text,p_quantity_dispatched numeric,p_expected_return_date date,
 p_sample_quantity numeric,p_remarks text
) returns jsonb
language plpgsql security definer set search_path=public,auth as $$
declare
 tid uuid:=public.current_tenant_id();
 stock public.supply_opening_stock%rowtype;
 specification_row public.part_process_specifications%rowtype;
 source_row public.production_batches%rowtype;
 child_row public.production_batches%rowtype;
 job_row public.osp_jobs%rowtype;
 job_number text; source_code text; child_code text; available_pcs numeric;
begin
 if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
 if not public.can_write_table('osp_jobs') then raise exception 'OSP Transactions create permission is required'; end if;
 select * into stock from public.supply_opening_stock where id=p_opening_stock_id and tenant_id=tid for update;
 if stock.id is null then raise exception 'Select a valid Opening Stock record'; end if;
 if stock.status<>'ACTIVE' or stock.stage not in ('MACHINING','OSP_READY','FINAL_INSPECTION','FINISHED_GOODS') then
   raise exception 'Only active part Opening Stock at a part/WIP stage can be dispatched to OSP';
 end if;
 available_pcs:=greatest(coalesce(stock.available_quantity_pcs,0),0);
 if coalesce(p_quantity_dispatched,0)<=0 or p_quantity_dispatched>available_pcs then
   raise exception 'OSP Material Out quantity % exceeds Opening Stock available quantity % pieces',p_quantity_dispatched,available_pcs;
 end if;
 select * into specification_row from public.part_process_specifications
 where id=p_process_specification_id and tenant_id=tid and part_id=stock.part_id and process_id=p_process_id and inward_type='OSP_PROCESS' and status='ACTIVE';
 if specification_row.id is null then raise exception 'The selected Part has no active OSP Process Specification for this Process'; end if;
 if nullif(btrim(coalesce(p_dispatch_challan,'')),'') is null then raise exception 'Material Out challan number is required'; end if;

 source_code:='OPEN-'||left(stock.id::text,8);
 select * into source_row from public.production_batches where tenant_id=tid and opening_stock_id=stock.id and batch_code=source_code for update;
 if source_row.id is null then
   insert into public.production_batches(tenant_id,batch_code,part_id,inward_lot_id,opening_stock_id,parent_batch_id,heat_number,heat_code,current_process_id,work_order,quantity_started,quantity_available,status,remarks)
   values(tid,source_code,stock.part_id,null,stock.id,null,coalesce(stock.heat_number,'OPENING'),coalesce(stock.heat_code,'OPENING'),null,'OPENING STOCK OSP SOURCE',stock.quantity_pcs,available_pcs,'RELEASED','Automatically created from QCMS Opening Stock')
   returning * into source_row;
 end if;
 job_number:=public.qsms_next_document_number('OSP_JOB'); child_code:=job_number||'-BATCH';
 insert into public.production_batches(tenant_id,batch_code,part_id,inward_lot_id,opening_stock_id,parent_batch_id,heat_number,heat_code,current_process_id,work_order,quantity_started,quantity_available,status,remarks)
 values(tid,child_code,stock.part_id,null,stock.id,source_row.id,coalesce(stock.heat_number,'OPENING'),coalesce(stock.heat_code,'OPENING'),p_process_id,job_number,p_quantity_dispatched,0,'AT_OSP','OSP vendor child batch from Opening Stock')
 returning * into child_row;
 insert into public.osp_jobs(tenant_id,osp_job_number,source_batch_id,osp_batch_id,source_inward_lot_id,opening_stock_id,part_id,vendor_id,process_id,process_specification_id,dispatch_date,dispatch_challan,quantity_dispatched,expected_return_date,process_specification,required_tests,sample_quantity,status,dispatch_remarks)
 values(tid,job_number,source_row.id,child_row.id,null,stock.id,stock.part_id,p_vendor_id,p_process_id,specification_row.id,p_dispatch_date,btrim(p_dispatch_challan),p_quantity_dispatched,p_expected_return_date,specification_row.process_specification,array_remove(array[case when specification_row.dimensional_required then 'DIMENSIONAL' end,case when specification_row.metlab_required then 'METLAB' end],null),coalesce(nullif(p_sample_quantity,0),specification_row.sample_quantity,1),'AT_VENDOR',nullif(btrim(coalesce(p_remarks,'')),''))
 returning * into job_row;
 update public.supply_opening_stock set available_quantity_pcs=greatest(available_pcs-p_quantity_dispatched,0),stage=case when available_pcs-p_quantity_dispatched<=0 then 'AT_OSP' else stage end,status=case when available_pcs-p_quantity_dispatched<=0 then 'CONSUMED' else status end,updated_at=now(),updated_by=auth.uid() where id=stock.id;
 update public.production_batches set quantity_available=greatest(available_pcs-p_quantity_dispatched,0),updated_at=now(),updated_by=auth.uid() where id=source_row.id;
 insert into public.batch_movements(tenant_id,batch_id,movement_type,from_process_id,to_process_id,quantity,movement_date,reference,remarks)
 values(tid,source_row.id,'OSP_DISPATCH',source_row.current_process_id,p_process_id,p_quantity_dispatched,p_dispatch_date,job_number,btrim(p_dispatch_challan));
 return to_jsonb(job_row)||jsonb_build_object('available_after_dispatch',greatest(available_pcs-p_quantity_dispatched,0),'source_type','OPENING_STOCK');
end;
$$;
revoke all on function public.qsms_create_osp_dispatch_from_opening_stock(uuid,uuid,uuid,uuid,date,text,numeric,date,numeric,text) from public,anon;
grant execute on function public.qsms_create_osp_dispatch_from_opening_stock(uuid,uuid,uuid,uuid,date,text,numeric,date,numeric,text) to authenticated;

commit;
