-- QCMS v4.14.19 — live Employee PO gate, universal transaction delete,
-- supplier PO confirmation + daily reminder, same-Heat RMTC continuity and image coverage.
-- Additive/backward-compatible. Existing production/master/quality/OSP/Supply Chain data is preserved.

begin;

-- 1) Supplier PO confirmation is a first-class Supply Chain transaction after PO approval.
create table if not exists public.supply_po_confirmations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  purchase_order_id uuid not null references public.supply_purchase_orders(id) on delete cascade,
  supplier_id uuid not null references public.parties(id) on delete restrict,
  confirmation_status text not null default 'PENDING'
    check (confirmation_status in ('PENDING','CONFIRMED','REVISION_REQUESTED','REJECTED','CANCELLED')),
  priority text not null default 'HIGH' check (priority in ('HIGH','NORMAL')),
  requested_at timestamptz not null default now(),
  confirmation_reference text,
  confirmation_date date,
  confirmed_delivery_date date,
  confirmed_at timestamptz,
  confirmed_by uuid references auth.users(id),
  reminder_count integer not null default 0 check (reminder_count >= 0),
  last_reminder_at timestamptz,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id),
  unique(tenant_id,purchase_order_id)
);
create index if not exists idx_supply_po_confirmation_status
  on public.supply_po_confirmations(tenant_id,confirmation_status,requested_at);
create index if not exists idx_supply_po_confirmation_supplier
  on public.supply_po_confirmations(tenant_id,supplier_id,confirmation_status);

-- Table/module mapping remains shared by UI and RLS.
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
 when target_table in ('supply_customer_orders','supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_po_confirmations','supply_opening_stock','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then 'SUPPLY_CHAIN'
 when target_table in ('user_module_permissions','user_section_permissions','department_module_defaults','role_module_defaults','qcms_module_approval_routes','supply_stage_responsibilities','qcms_user_activity_log') then 'USER_ACCESS'
 else upper(target_table) end;
$$;

alter table public.supply_po_confirmations enable row level security;
drop policy if exists tenant_select on public.supply_po_confirmations;
create policy tenant_select on public.supply_po_confirmations
for select to authenticated using (
  tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('SUPPLY_CHAIN','view')
);
drop policy if exists tenant_insert on public.supply_po_confirmations;
create policy tenant_insert on public.supply_po_confirmations
for insert to authenticated with check (
  tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('SUPPLY_CHAIN','create')
);
drop policy if exists tenant_update on public.supply_po_confirmations;
create policy tenant_update on public.supply_po_confirmations
for update to authenticated
using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('SUPPLY_CHAIN','edit'))
with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('SUPPLY_CHAIN','edit'));
drop policy if exists tenant_delete on public.supply_po_confirmations;
create policy tenant_delete on public.supply_po_confirmations
for delete to authenticated using (
  tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('SUPPLY_CHAIN','archive')
);
grant select,insert,update,delete on public.supply_po_confirmations to authenticated;

-- Attachment authorization for supplier acknowledgement files.
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
 else null end;
$$;

-- Create/repair a confirmation row without mutating the PO or supplier.
create or replace function public.qcms_ensure_po_confirmation(p_purchase_order_id uuid)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare
  tid uuid:=public.current_tenant_id();
  po public.supply_purchase_orders%rowtype;
  conf public.supply_po_confirmations%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('SUPPLY_CHAIN','view') then raise exception 'Supply Chain View permission is required'; end if;
  select * into po from public.supply_purchase_orders where id=p_purchase_order_id and tenant_id=tid;
  if po.id is null then raise exception 'Purchase Order was not found'; end if;
  if coalesce(po.approval_status,'PENDING_APPROVAL')<>'APPROVED' then raise exception 'Supplier confirmation starts after Purchase Order approval'; end if;
  insert into public.supply_po_confirmations(tenant_id,purchase_order_id,supplier_id,confirmation_status,priority,requested_at)
  values(tid,po.id,po.supplier_id,case when po.status='CANCELLED' then 'CANCELLED' else 'PENDING' end,'HIGH',now())
  on conflict(tenant_id,purchase_order_id) do update set
    supplier_id=excluded.supplier_id,
    confirmation_status=case when public.supply_po_confirmations.confirmation_status='CANCELLED' and po.status<>'CANCELLED' then 'PENDING' else public.supply_po_confirmations.confirmation_status end,
    updated_at=now()
  returning * into conf;
  return to_jsonb(conf);
end $$;
revoke all on function public.qcms_ensure_po_confirmation(uuid) from public,anon;
grant execute on function public.qcms_ensure_po_confirmation(uuid) to authenticated;

-- DB trigger guarantees every approved PO enters confirmation follow-up even if approval happens outside Streamlit UI.
create or replace function public.qcms_sync_po_confirmation_stage()
returns trigger language plpgsql set search_path='public','auth' as $$
begin
  if new.approval_status='APPROVED' and new.status<>'CANCELLED' then
    insert into public.supply_po_confirmations(tenant_id,purchase_order_id,supplier_id,confirmation_status,priority,requested_at)
    values(new.tenant_id,new.id,new.supplier_id,'PENDING','HIGH',coalesce(new.approved_at,now()))
    on conflict(tenant_id,purchase_order_id) do update set
      supplier_id=excluded.supplier_id,
      confirmation_status=case when public.supply_po_confirmations.confirmation_status='CANCELLED' then 'PENDING' else public.supply_po_confirmations.confirmation_status end,
      updated_at=now();
  elsif new.status='CANCELLED' then
    update public.supply_po_confirmations set confirmation_status='CANCELLED',updated_at=now(),updated_by=auth.uid()
    where tenant_id=new.tenant_id and purchase_order_id=new.id and confirmation_status<>'CONFIRMED';
  end if;
  return new;
end $$;
drop trigger if exists trg_qcms_po_confirmation_stage on public.supply_purchase_orders;
create trigger trg_qcms_po_confirmation_stage
after insert or update of approval_status,status,supplier_id on public.supply_purchase_orders
for each row execute function public.qcms_sync_po_confirmation_stage();

-- Backfill confirmation follow-up for existing approved/open POs without changing their execution status.
insert into public.supply_po_confirmations(tenant_id,purchase_order_id,supplier_id,confirmation_status,priority,requested_at)
select po.tenant_id,po.id,po.supplier_id,'PENDING','HIGH',coalesce(po.approved_at,po.updated_at,po.created_at,now())
from public.supply_purchase_orders po
where po.approval_status='APPROVED' and po.status not in ('CANCELLED','CLOSED')
on conflict(tenant_id,purchase_order_id) do nothing;

-- Confirmation can be finalized only after an attachment exists.
create or replace function public.qcms_confirm_purchase_order(
  p_purchase_order_id uuid,
  p_confirmation_reference text,
  p_confirmation_date date,
  p_confirmed_delivery_date date default null,
  p_remarks text default null
)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare
  tid uuid:=public.current_tenant_id();
  po public.supply_purchase_orders%rowtype;
  conf public.supply_po_confirmations%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('SUPPLY_CHAIN','edit') then raise exception 'Supply Chain Edit permission is required'; end if;
  if nullif(btrim(coalesce(p_confirmation_reference,'')),'') is null then raise exception 'Supplier Confirmation Reference is required'; end if;
  if p_confirmation_date is null then raise exception 'Supplier Confirmation Date is required'; end if;
  select * into po from public.supply_purchase_orders where id=p_purchase_order_id and tenant_id=tid for update;
  if po.id is null then raise exception 'Purchase Order was not found'; end if;
  if coalesce(po.approval_status,'PENDING_APPROVAL')<>'APPROVED' then raise exception 'Purchase Order must be approved before supplier confirmation'; end if;
  if po.status='CANCELLED' then raise exception 'Cancelled Purchase Order cannot be supplier-confirmed'; end if;
  insert into public.supply_po_confirmations(tenant_id,purchase_order_id,supplier_id,confirmation_status,priority,requested_at)
  values(tid,po.id,po.supplier_id,'PENDING','HIGH',coalesce(po.approved_at,now()))
  on conflict(tenant_id,purchase_order_id) do update set supplier_id=excluded.supplier_id,updated_at=now()
  returning * into conf;
  if not exists(
    select 1 from public.document_attachments a
    where a.tenant_id=tid and a.entity_type='PO_CONFIRMATION' and a.entity_id=conf.id
      and a.document_type='SUPPLIER_PO_CONFIRMATION' and a.status='ACTIVE'
  ) then
    raise exception 'Upload the Supplier PO Confirmation attachment before confirming the PO';
  end if;
  update public.supply_po_confirmations set
    confirmation_status='CONFIRMED',confirmation_reference=btrim(p_confirmation_reference),
    confirmation_date=p_confirmation_date,confirmed_delivery_date=p_confirmed_delivery_date,
    confirmed_at=now(),confirmed_by=auth.uid(),remarks=nullif(btrim(coalesce(p_remarks,'')),''),
    updated_at=now(),updated_by=auth.uid()
  where id=conf.id returning * into conf;
  return to_jsonb(conf);
end $$;
revoke all on function public.qcms_confirm_purchase_order(uuid,text,date,date,text) from public,anon;
grant execute on function public.qcms_confirm_purchase_order(uuid,text,date,date,text) to authenticated;

-- 2) Unified transaction delete by module Delete/Archive permission.
-- OSP jobs/receipts are excluded here because their dedicated RPCs reverse stock allocations safely.
create or replace function public.qcms_delete_transaction_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare
  tid uuid:=public.current_tenant_id();
  module_name text:=public.qsms_module_for_table(p_table_name);
  deleted_count integer:=0;
  allowed_tables constant text[]:=array[
    'supply_customer_orders','supply_purchase_orders','supply_po_confirmations','supply_rm_purchase_orders','supply_rm_receipts','supply_rm_dispatches','supply_forging_orders','supply_forging_receipts','supply_downstream_events','supply_opening_stock',
    'rmtc_approvals','inward_lots','inspection_reports','lab_tests','npd_orders','npd_process_flows','ppap_projects','pfd_headers','pfmea_headers','control_plan_headers','spc_studies','msa_studies','capacity_studies','qc_calculation_records','quality_complaints'
  ];
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if p_table_name is null or not (p_table_name=any(allowed_tables)) then raise exception 'Controlled transaction deletion is not enabled for this record type'; end if;
  if not public.qcms_effective_module_permission(module_name,'archive') then raise exception 'Delete/Archive permission is not assigned for %',module_name; end if;
  execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
  get diagnostics deleted_count=row_count;
  if deleted_count=0 then raise exception 'Selected transaction was not found or is outside your company tenant'; end if;
  return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id,'module',module_name,'deleted_by',auth.uid());
exception
  when foreign_key_violation then
    raise exception 'This transaction has downstream linked records. Delete or reverse the dependent stage first; QCMS will not break genealogy.';
end $$;
revoke all on function public.qcms_delete_transaction_row(text,uuid) from public,anon;
grant execute on function public.qcms_delete_transaction_row(text,uuid) to authenticated;

-- 3) Same-Heat RMTC explicit guard: multiple certificates are allowed. Only an exact
-- Heat + Supplier RMTC/TC duplicate is rejected, and every certificate reuses the canonical Heat Code.
-- The existing unique partial index already expresses this rule; reassert it for deployment verification.
drop index if exists public.uq_rmtc_heat_supplier_rmtc_number;
create unique index uq_rmtc_heat_supplier_rmtc_number
on public.rmtc_approvals(tenant_id,normalized_heat_number,normalized_supplier_rmtc_number)
where normalized_supplier_rmtc_number<>'';

create or replace function public.qcms_enforce_same_heat_code()
returns trigger language plpgsql set search_path='public','auth' as $$
declare canonical_code text;
begin
  new.normalized_heat_number:=public.qsms_normalize_heat_number(new.heat_number);
  if new.normalized_heat_number='' then return new; end if;
  select nullif(btrim(r.heat_code),'') into canonical_code
  from public.rmtc_approvals r
  where r.tenant_id=new.tenant_id and r.normalized_heat_number=new.normalized_heat_number
    and r.id<>new.id and nullif(btrim(coalesce(r.heat_code,'')),'') is not null
  order by r.created_at,r.id limit 1;
  if canonical_code is not null then new.heat_code:=canonical_code; end if;
  return new;
end $$;
drop trigger if exists trg_qcms_same_heat_code on public.rmtc_approvals;
create trigger trg_qcms_same_heat_code before insert or update of heat_number,heat_code on public.rmtc_approvals
for each row execute function public.qcms_enforce_same_heat_code();

-- 4) Supplier confirmation notification templates/routes and daily high-priority schedule.
insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,v.template_key,'SUPPLY_CHAIN',v.template_name,v.subject_template,v.body_template,v.include_pdf,v.include_docs,v.include_supplier,true
from public.tenants t cross join (values
 ('PO_CONFIRMATION_REQUIRED','Supplier PO Confirmation Required','PRIORITY · Purchase Order confirmation required · {{document_no}}',
  'Dear Supplier,\n\nPlease confirm Purchase Order {{document_no}} on priority and return your acknowledgement / confirmation. QCMS will continue a daily reminder until confirmation is recorded.\n\nSupplier: {{supplier_name}}\nRequired next stage: Supplier PO Confirmation\n\nRegards,\nFour Star Industries · QCMS',true,true,true),
 ('PO_CONFIRMATION_RECEIVED','Supplier PO Confirmation Received','QCMS · Supplier PO confirmation received · {{document_no}}',
  'Supplier confirmation has been recorded for Purchase Order {{document_no}}.\nConfirmation Reference: {{confirmation_reference}}\nNext stage: {{next_stage}}\n\nRegards,\nQCMS',true,true,false),
 ('PO_CONFIRMATION_DAILY_DIGEST','Daily Priority Supplier PO Confirmation','PRIORITY · Purchase Order confirmation pending · {{report_date}}',
  'Dear Supplier,\n\nThis is the daily priority reminder for Purchase Order confirmation(s) still pending in QCMS. Please send your PO acknowledgement / confirmation immediately.\nPending confirmations: {{open_count}}\nReport Date: {{report_date}}\n\nThe attached report lists the pending Purchase Orders. Daily reminders stop automatically once confirmation is recorded.\n\nRegards,\nFour Star Industries · QCMS',true,false,true)
) v(template_key,template_name,subject_template,body_template,include_pdf,include_docs,include_supplier)
on conflict(tenant_id,template_key) do update set
 module_key=excluded.module_key,template_name=excluded.template_name,subject_template=excluded.subject_template,
 body_template=excluded.body_template,include_generated_pdf=excluded.include_generated_pdf,
 include_record_attachments=excluded.include_record_attachments,include_supplier=excluded.include_supplier,enabled=true,updated_at=now();

insert into public.qcms_notification_routes
(tenant_id,event_key,route_label,department,department_cc,send_to_supplier,template_key,next_stage,enabled)
select t.id,v.event_key,v.route_label,'Supply Chain',true,v.send_supplier,v.template_key,v.next_stage,true
from public.tenants t cross join (values
 ('PO_CONFIRMATION_REQUIRED','Supplier PO confirmation required',true,'PO_CONFIRMATION_REQUIRED','Supplier PO Confirmation'),
 ('PO_CONFIRMATION_RECEIVED','Supplier PO confirmation received',false,'PO_CONFIRMATION_RECEIVED','RM / Forging Receipt Execution')
) v(event_key,route_label,send_supplier,template_key,next_stage)
on conflict(tenant_id,event_key) do update set
 route_label=excluded.route_label,department=coalesce(public.qcms_notification_routes.department,excluded.department),
 department_cc=excluded.department_cc,send_to_supplier=excluded.send_to_supplier,template_key=excluded.template_key,
 next_stage=excluded.next_stage,enabled=true,updated_at=now();

insert into public.qcms_notification_schedules
(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,include_suppliers,template_key)
select t.id,'PO_CONFIRMATION_DAILY','SUPPLY_CHAIN','PO_CONFIRMATION_REQUIRED','PRIORITY · Supplier PO Confirmation Pending',true,8,'Asia/Kolkata',365,true,true,'Supply Chain',true,'PO_CONFIRMATION_DAILY_DIGEST'
from public.tenants t
on conflict(tenant_id,schedule_key) do update set
 module_key=excluded.module_key,event_key=excluded.event_key,schedule_label=excluded.schedule_label,enabled=true,
 hour_local=excluded.hour_local,timezone=excluded.timezone,days_ahead=excluded.days_ahead,
 include_overdue=true,include_open=true,recipient_department=excluded.recipient_department,
 include_suppliers=true,template_key=excluded.template_key,updated_at=now();

-- Dedicated daily supplier-confirmation reminder. Existing general overdue notifier remains unchanged.
do $$ declare jid bigint; begin
  select jobid into jid from cron.job where jobname='qcms-po-confirmation-reminder-daily' limit 1;
  if jid is not null then perform cron.unschedule(jid); end if;
end $$;
select cron.schedule('qcms-po-confirmation-reminder-daily','30 2 * * *',$cron$
select net.http_post(
 url := (select decrypted_secret from vault.decrypted_secrets where name='qcms_project_url' order by created_at desc limit 1) || '/functions/v1/qcms-po-confirmation-reminder',
 headers := jsonb_build_object('Content-Type','application/json','X-QCMS-Scheduler',(select decrypted_secret from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1)),
 body := jsonb_build_object('source','supabase_cron','schedule','PO_CONFIRMATION_DAILY','requested_at',now()),
 timeout_milliseconds := 30000
) as request_id;
$cron$);

-- Supply Chain stage responsibility registry includes supplier acknowledgement.
insert into public.supply_stage_responsibilities
(tenant_id,stage_key,stage_label,department,employee_id,notify_supplier,enabled)
select t.id,'SUPPLIER_PO_CONFIRMATION','Supplier Purchase Order Confirmation','Supply Chain',null,true,true
from public.tenants t
on conflict(tenant_id,stage_key) do update set
 stage_label=excluded.stage_label,department=coalesce(public.supply_stage_responsibilities.department,excluded.department),
 notify_supplier=true,enabled=true,updated_at=now();

-- 5) Audit trigger for new table; comprehensive audit remains authoritative.
drop trigger if exists trg_audit_row_change on public.supply_po_confirmations;
create trigger trg_audit_row_change after insert or update or delete on public.supply_po_confirmations
for each row execute function public.log_row_change();

-- 6) Shared supplier RM / forging item identity across multiple finished Parts.
alter table public.part_raw_material_details
  add column if not exists supplier_rm_item_code text,
  add column if not exists supplier_forging_part_number text;
comment on column public.part_raw_material_details.supplier_rm_item_code is 'Common supplier-facing RM item code; may intentionally repeat across different finished Parts using identical RM.';
comment on column public.part_raw_material_details.supplier_forging_part_number is 'Common supplier forging part number; may intentionally repeat across different finished Parts using the same purchased forging.';
create index if not exists idx_part_rm_supplier_common_rm on public.part_raw_material_details(tenant_id,supplier_id,lower(supplier_rm_item_code)) where nullif(btrim(supplier_rm_item_code),'') is not null;
create index if not exists idx_part_rm_supplier_common_forging on public.part_raw_material_details(tenant_id,supplier_id,lower(supplier_forging_part_number)) where nullif(btrim(supplier_forging_part_number),'') is not null;

alter table public.supply_purchase_order_items
  add column if not exists supplier_item_code_snapshot text,
  add column if not exists linked_finished_parts_snapshot jsonb not null default '[]'::jsonb;
alter table public.supply_forging_orders
  add column if not exists purchase_order_item_id uuid references public.supply_purchase_order_items(id) on delete restrict;
drop index if exists public.uq_supply_forging_supplier_order_no;
create unique index if not exists uq_supply_forging_supplier_order_source
  on public.supply_forging_orders(tenant_id,forging_supplier_id,lower(supplier_order_no),customer_order_id)
  where status<>'CANCELLED';

-- 7) Supplier PO confirmation is a real gate before receipt execution. Existing POs that
-- already have receipt genealogy are grandfathered as confirmed; no historical transaction is blocked.
update public.supply_po_confirmations c set
  confirmation_status='CONFIRMED', confirmation_reference=coalesce(c.confirmation_reference,'LEGACY RECEIPT EXISTS'),
  confirmation_date=coalesce(c.confirmation_date,current_date), confirmed_at=coalesce(c.confirmed_at,now()),
  remarks=coalesce(c.remarks,'Automatically grandfathered because receipt genealogy existed before v4.14.19.'), updated_at=now()
where c.confirmation_status<>'CONFIRMED' and exists(
  select 1 from public.supply_rm_purchase_orders rpo join public.supply_rm_receipts rr on rr.rm_purchase_order_id=rpo.id
  where rpo.purchase_order_id=c.purchase_order_id
  union all
  select 1 from public.supply_forging_orders fo join public.supply_forging_receipts fr on fr.forging_order_id=fo.id
  where fo.purchase_order_id=c.purchase_order_id
);

create or replace function public.qcms_require_supplier_po_confirmation()
returns trigger language plpgsql security definer set search_path='public','auth' as $$
declare controlled_po uuid; confirmation text;
begin
  if tg_table_name='supply_rm_receipts' then
    select purchase_order_id into controlled_po from public.supply_rm_purchase_orders where id=new.rm_purchase_order_id and tenant_id=new.tenant_id;
  elsif tg_table_name='supply_forging_receipts' then
    select purchase_order_id into controlled_po from public.supply_forging_orders where id=new.forging_order_id and tenant_id=new.tenant_id;
  end if;
  if controlled_po is null then return new; end if;
  select confirmation_status into confirmation from public.supply_po_confirmations where tenant_id=new.tenant_id and purchase_order_id=controlled_po order by created_at desc limit 1;
  if coalesce(confirmation,'PENDING')<>'CONFIRMED' then
    raise exception 'Supplier PO Confirmation is pending. Upload and record the supplier acknowledgement before receipt execution.';
  end if;
  return new;
end $$;
drop trigger if exists trg_qcms_rm_receipt_po_confirmation on public.supply_rm_receipts;
create trigger trg_qcms_rm_receipt_po_confirmation before insert or update of rm_purchase_order_id on public.supply_rm_receipts for each row execute function public.qcms_require_supplier_po_confirmation();
drop trigger if exists trg_qcms_forging_receipt_po_confirmation on public.supply_forging_receipts;
create trigger trg_qcms_forging_receipt_po_confirmation before insert or update of forging_order_id on public.supply_forging_receipts for each row execute function public.qcms_require_supplier_po_confirmation();
revoke all on function public.qcms_require_supplier_po_confirmation() from public,anon,authenticated;

-- 8) Reassert Standalone MetLAB / Dimensional RLS against the same effective permission engine used by the UI.
drop policy if exists tenant_insert on public.lab_tests;
create policy tenant_insert on public.lab_tests for insert to authenticated with check(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('METLAB_REPORT','create'));
drop policy if exists tenant_update on public.lab_tests;
create policy tenant_update on public.lab_tests for update to authenticated using(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('METLAB_REPORT','edit')) with check(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('METLAB_REPORT','edit'));
drop policy if exists tenant_insert on public.inspection_reports;
create policy tenant_insert on public.inspection_reports for insert to authenticated with check(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('DIMENSIONAL_REPORT','create'));
drop policy if exists tenant_update on public.inspection_reports;
create policy tenant_update on public.inspection_reports for update to authenticated using(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('DIMENSIONAL_REPORT','edit')) with check(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('DIMENSIONAL_REPORT','edit'));

-- 9) Generic transaction delete routes OSP to its safe reversal functions.
create or replace function public.qcms_delete_transaction_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare tid uuid:=public.current_tenant_id(); module_name text:=public.qsms_module_for_table(p_table_name); deleted_count integer:=0;
allowed_tables constant text[]:=array['supply_customer_orders','supply_purchase_orders','supply_po_confirmations','supply_rm_purchase_orders','supply_rm_receipts','supply_rm_dispatches','supply_forging_orders','supply_forging_receipts','supply_downstream_events','supply_opening_stock','osp_jobs','osp_receipts','rmtc_approvals','inward_lots','inspection_reports','lab_tests','npd_orders','npd_process_flows','ppap_projects','pfd_headers','pfmea_headers','control_plan_headers','spc_studies','msa_studies','capacity_studies','qc_calculation_records','quality_complaints'];
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

-- 10) Daily pending Purchase Order approval and RM Procurement due/overdue worklists.
insert into public.qcms_email_templates(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,v.k,'SUPPLY_CHAIN',v.n,v.s,v.b,true,false,false,true from public.tenants t cross join(values
 ('PO_PENDING_APPROVAL','Pending Purchase Order Approval','QCMS · Purchase Orders pending approval · {{report_date}}','Pending Purchase Orders requiring approval are attached. Pending: {{open_count}} · Report Date: {{report_date}}.'),
 ('RM_PROCUREMENT_PENDING_DUE','RM Procurement PO Pending / Due / Overdue','QCMS · RM procurement PO pending / due / overdue · {{report_date}}','Customer Orders still requiring RM Purchase Orders are attached. Open/Due: {{open_count}} · Overdue: {{overdue_count}} · Report Date: {{report_date}}.')
) v(k,n,s,b) on conflict(tenant_id,template_key) do update set module_key=excluded.module_key,template_name=excluded.template_name,subject_template=excluded.subject_template,body_template=excluded.body_template,include_generated_pdf=true,enabled=true,updated_at=now();

insert into public.qcms_notification_schedules(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,include_suppliers,template_key)
select t.id,v.k,'SUPPLY_CHAIN',v.e,v.l,true,8,'Asia/Kolkata',v.d,true,true,'Supply Chain',false,v.k from public.tenants t cross join(values
 ('PO_PENDING_APPROVAL','PO_PENDING_APPROVAL','Purchase Orders Pending Approval',365),
 ('RM_PROCUREMENT_PENDING_DUE','RM_PROCUREMENT_PENDING','RM Procurement PO Pending / Due / Overdue',30)
) v(k,e,l,d) on conflict(tenant_id,schedule_key) do update set module_key=excluded.module_key,event_key=excluded.event_key,schedule_label=excluded.schedule_label,enabled=true,hour_local=8,timezone='Asia/Kolkata',days_ahead=excluded.days_ahead,include_overdue=true,include_open=true,recipient_department='Supply Chain',include_suppliers=false,template_key=excluded.template_key,updated_at=now();

-- 11) Release marker used by the one-file deployment guard.
create or replace function public.qcms_release_schema_version()
returns text language sql immutable security invoker set search_path='pg_catalog'
as $$ select '4.14.19'::text $$;
revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to anon,authenticated;

-- Full v4.14.19 public release contract for the one-file updater. This exposes only a readiness marker, never business data.
create or replace function public.qcms_release_contract_v41419()
returns text language plpgsql stable security definer set search_path='public','pg_catalog' as $$
begin
  if to_regclass('public.supply_po_confirmations') is not null
     and to_regprocedure('public.qcms_ensure_po_confirmation(uuid)') is not null
     and to_regprocedure('public.qcms_confirm_purchase_order(uuid,text,date,date,text)') is not null
     and to_regprocedure('public.qcms_delete_transaction_row(text,uuid)') is not null
     and to_regprocedure('public.qcms_require_supplier_po_confirmation()') is not null
     and exists(select 1 from information_schema.columns where table_schema='public' and table_name='part_raw_material_details' and column_name='supplier_rm_item_code')
     and exists(select 1 from information_schema.columns where table_schema='public' and table_name='part_raw_material_details' and column_name='supplier_forging_part_number')
     and exists(select 1 from information_schema.columns where table_schema='public' and table_name='supply_purchase_order_items' and column_name='linked_finished_parts_snapshot')
     and exists(select 1 from information_schema.columns where table_schema='public' and table_name='supply_forging_orders' and column_name='purchase_order_item_id')
     and exists(select 1 from public.qcms_notification_schedules where schedule_key='PO_CONFIRMATION_DAILY' and enabled)
     and exists(select 1 from public.qcms_notification_schedules where schedule_key='PO_PENDING_APPROVAL' and enabled)
     and exists(select 1 from public.qcms_notification_schedules where schedule_key='RM_PROCUREMENT_PENDING_DUE' and enabled)
     and exists(select 1 from pg_policies where schemaname='public' and tablename='lab_tests' and policyname='tenant_insert' and coalesce(with_check,'') like '%METLAB_REPORT%')
     and exists(select 1 from pg_policies where schemaname='public' and tablename='lab_tests' and policyname='tenant_update' and coalesce(qual,'') like '%METLAB_REPORT%')
  then return 'QCMS_V41419_FULL_READY';
  end if;
  return 'QCMS_V41419_INCOMPLETE';
end $$;
revoke all on function public.qcms_release_contract_v41419() from public;
grant execute on function public.qcms_release_contract_v41419() to anon,authenticated;

insert into public.qcms_release_schema_state(version,build,applied_at,details)
values ('4.14.19','41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES',now(),
 jsonb_build_object(
   'po_live_employee_resolver',true,
   'universal_transaction_delete',true,
   'osp_delete_permission_preserved',true,
   'user_and_entry_status_columns',true,
   'employee_link_persistence',true,
   'same_heat_multiple_rmtc',true,
   'microstructure_bmp_tiff_webp_gif',true,
   'supplier_po_confirmation',true,
   'daily_supplier_confirmation_reminder',true,
   'common_rm_and_forging_multi_part_po',true,
   'supplier_confirmation_receipt_gate',true,
   'pending_po_rm_procurement_daily_notices',true,
   'standalone_metlab_rls_reasserted',true,
   'data_reset',false
 ))
on conflict(version) do update set build=excluded.build,applied_at=excluded.applied_at,details=excluded.details;

commit;
