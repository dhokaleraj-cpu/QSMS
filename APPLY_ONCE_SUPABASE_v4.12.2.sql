-- QCMS v4.12.2 — Supply Chain master-linked traceability and Material Inward bridge
-- ADDITIVE ONLY. No existing transaction, RMTC, inward, inspection or master data is reset/deleted.
begin;

-- -----------------------------------------------------------------------------
-- 1) Material Inward becomes the single controlled source for RM Receipt.
-- -----------------------------------------------------------------------------
alter table public.inward_lots
  add column if not exists supply_customer_order_id uuid references public.supply_customer_orders(id) on delete restrict,
  add column if not exists supply_rm_purchase_order_id uuid references public.supply_rm_purchase_orders(id) on delete restrict;

alter table public.supply_rm_receipts
  add column if not exists inward_lot_id uuid references public.inward_lots(id) on delete restrict,
  add column if not exists heat_code text,
  add column if not exists rmtc_number text,
  add column if not exists rmtc_date date,
  add column if not exists rmtc_qty_kg numeric(18,3);

alter table public.supply_rm_dispatches
  add column if not exists rm_receipt_id uuid references public.supply_rm_receipts(id) on delete restrict,
  add column if not exists inward_lot_id uuid references public.inward_lots(id) on delete restrict,
  add column if not exists heat_code text;

alter table public.supply_forging_orders
  add column if not exists rm_dispatch_id uuid references public.supply_rm_dispatches(id) on delete restrict,
  add column if not exists inward_lot_id uuid references public.inward_lots(id) on delete restrict,
  add column if not exists heat_number text,
  add column if not exists heat_code text;

alter table public.supply_forging_receipts
  add column if not exists rm_dispatch_id uuid references public.supply_rm_dispatches(id) on delete restrict,
  add column if not exists inward_lot_id uuid references public.inward_lots(id) on delete restrict,
  add column if not exists heat_number text,
  add column if not exists heat_code text;

alter table public.supply_downstream_events
  add column if not exists source_forging_receipt_id uuid references public.supply_forging_receipts(id) on delete restrict,
  add column if not exists source_event_id uuid references public.supply_downstream_events(id) on delete restrict,
  add column if not exists inward_lot_id uuid references public.inward_lots(id) on delete restrict,
  add column if not exists heat_number text,
  add column if not exists heat_code text;

create index if not exists idx_inward_supply_order on public.inward_lots(tenant_id,supply_customer_order_id);
create index if not exists idx_inward_supply_rm_po on public.inward_lots(tenant_id,supply_rm_purchase_order_id);
create unique index if not exists uq_supply_rm_receipt_inward
  on public.supply_rm_receipts(tenant_id,inward_lot_id) where inward_lot_id is not null;
create index if not exists idx_supply_rm_receipt_heat on public.supply_rm_receipts(tenant_id,heat_number);
create index if not exists idx_supply_rm_dispatch_receipt on public.supply_rm_dispatches(tenant_id,rm_receipt_id);
create index if not exists idx_supply_forging_order_dispatch on public.supply_forging_orders(tenant_id,rm_dispatch_id);
create index if not exists idx_supply_forging_receipt_dispatch on public.supply_forging_receipts(tenant_id,rm_dispatch_id);
create index if not exists idx_supply_downstream_inward on public.supply_downstream_events(tenant_id,inward_lot_id);
create index if not exists idx_supply_downstream_heat on public.supply_downstream_events(tenant_id,heat_number);

-- -----------------------------------------------------------------------------
-- 2) Database-side lineage poka-yoke. The UI inherits these values, and the DB
--    independently prevents a broken customer-order / part / Heat genealogy.
-- -----------------------------------------------------------------------------
create or replace function public.qcms_supply_validate_inward_link()
returns trigger language plpgsql security definer set search_path=public as $$
declare expected_order uuid; expected_part uuid;
begin
  if new.supply_rm_purchase_order_id is null then
    return new;
  end if;
  select po.customer_order_id,o.part_id into expected_order,expected_part
  from public.supply_rm_purchase_orders po
  join public.supply_customer_orders o on o.id=po.customer_order_id
  where po.id=new.supply_rm_purchase_order_id and po.tenant_id=new.tenant_id;
  if expected_order is null then raise exception 'Linked RM Procurement record is invalid for this tenant'; end if;
  if new.part_id is distinct from expected_part then
    raise exception 'Material Inward Part Number must match the Part Number linked to RM Procurement';
  end if;
  new.supply_customer_order_id:=expected_order;
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_validate_inward_link on public.inward_lots;
create trigger trg_qcms_supply_validate_inward_link
before insert or update of supply_rm_purchase_order_id,supply_customer_order_id,part_id
on public.inward_lots for each row execute function public.qcms_supply_validate_inward_link();

create or replace function public.qcms_supply_inherit_rm_receipt()
returns trigger language plpgsql security definer set search_path=public as $$
declare i public.inward_lots%rowtype; po public.supply_rm_purchase_orders%rowtype; r public.rmtc_approvals%rowtype;
begin
  if new.inward_lot_id is null then return new; end if;
  select * into i from public.inward_lots where id=new.inward_lot_id and tenant_id=new.tenant_id;
  if i.id is null then raise exception 'Linked Material Inward record is invalid'; end if;
  if i.supply_rm_purchase_order_id is null then raise exception 'Material Inward must be linked to RM Procurement before RM Receipt genealogy can be posted'; end if;
  select * into po from public.supply_rm_purchase_orders where id=i.supply_rm_purchase_order_id and tenant_id=new.tenant_id;
  if po.id is null then raise exception 'Linked RM Procurement record is invalid'; end if;
  select * into r from public.rmtc_approvals where id=i.rmtc_approval_id and tenant_id=new.tenant_id;
  new.customer_order_id:=po.customer_order_id;
  new.rm_purchase_order_id:=po.id;
  new.receipt_number:=coalesce(nullif(btrim(new.receipt_number),''),i.inward_number);
  new.receipt_date:=coalesce(new.receipt_date,i.inward_date);
  new.heat_number:=i.heat_number;
  new.heat_code:=i.heat_code;
  new.received_qty_kg:=coalesce(i.steel_quantity_kg,i.quantity_received,new.received_qty_kg);
  new.supplier_challan:=coalesce(nullif(btrim(new.supplier_challan),''),i.grn_number);
  new.rmtc_number:=coalesce(r.rmtc_number,new.rmtc_number);
  new.rmtc_date:=coalesce(r.certificate_date,new.rmtc_date);
  new.rmtc_qty_kg:=coalesce(r.certificate_quantity,new.rmtc_qty_kg);
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_inherit_rm_receipt on public.supply_rm_receipts;
create trigger trg_qcms_supply_inherit_rm_receipt
before insert or update of inward_lot_id,customer_order_id,rm_purchase_order_id,heat_number,heat_code,received_qty_kg,rmtc_number,rmtc_date,rmtc_qty_kg
on public.supply_rm_receipts for each row execute function public.qcms_supply_inherit_rm_receipt();

create or replace function public.qcms_supply_inherit_rm_dispatch()
returns trigger language plpgsql security definer set search_path=public as $$
declare src public.supply_rm_receipts%rowtype; o public.supply_customer_orders%rowtype;
begin
  if new.rm_receipt_id is null then return new; end if;
  select * into src from public.supply_rm_receipts where id=new.rm_receipt_id and tenant_id=new.tenant_id;
  if src.id is null then raise exception 'Linked RM Receipt / Material Inward source is invalid'; end if;
  select * into o from public.supply_customer_orders where id=src.customer_order_id and tenant_id=new.tenant_id;
  new.customer_order_id:=src.customer_order_id;
  new.inward_lot_id:=src.inward_lot_id;
  new.heat_number:=src.heat_number;
  new.heat_code:=src.heat_code;
  if o.forging_supplier_id is not null then new.forging_supplier_id:=o.forging_supplier_id; end if;
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_inherit_rm_dispatch on public.supply_rm_dispatches;
create trigger trg_qcms_supply_inherit_rm_dispatch
before insert or update of rm_receipt_id,customer_order_id,inward_lot_id,heat_number,heat_code
on public.supply_rm_dispatches for each row execute function public.qcms_supply_inherit_rm_dispatch();

create or replace function public.qcms_supply_inherit_forging_order()
returns trigger language plpgsql security definer set search_path=public as $$
declare src public.supply_rm_dispatches%rowtype; o public.supply_customer_orders%rowtype;
begin
  if new.rm_dispatch_id is null then return new; end if;
  select * into src from public.supply_rm_dispatches where id=new.rm_dispatch_id and tenant_id=new.tenant_id;
  if src.id is null then raise exception 'Linked RM-to-Forging dispatch is invalid'; end if;
  select * into o from public.supply_customer_orders where id=src.customer_order_id and tenant_id=new.tenant_id;
  new.customer_order_id:=src.customer_order_id;
  new.inward_lot_id:=src.inward_lot_id;
  new.heat_number:=src.heat_number;
  new.heat_code:=src.heat_code;
  if o.forging_supplier_id is not null then new.forging_supplier_id:=o.forging_supplier_id; end if;
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_inherit_forging_order on public.supply_forging_orders;
create trigger trg_qcms_supply_inherit_forging_order
before insert or update of rm_dispatch_id,customer_order_id,inward_lot_id,heat_number,heat_code
on public.supply_forging_orders for each row execute function public.qcms_supply_inherit_forging_order();

create or replace function public.qcms_supply_inherit_forging_receipt()
returns trigger language plpgsql security definer set search_path=public as $$
declare src public.supply_forging_orders%rowtype;
begin
  select * into src from public.supply_forging_orders where id=new.forging_order_id and tenant_id=new.tenant_id;
  if src.id is null then raise exception 'Linked Forging Order is invalid'; end if;
  new.customer_order_id:=src.customer_order_id;
  new.rm_dispatch_id:=src.rm_dispatch_id;
  new.inward_lot_id:=src.inward_lot_id;
  new.forging_supplier_id:=src.forging_supplier_id;
  new.heat_number:=src.heat_number;
  new.heat_code:=src.heat_code;
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_inherit_forging_receipt on public.supply_forging_receipts;
create trigger trg_qcms_supply_inherit_forging_receipt
before insert or update of forging_order_id,customer_order_id,rm_dispatch_id,inward_lot_id,heat_number,heat_code
on public.supply_forging_receipts for each row execute function public.qcms_supply_inherit_forging_receipt();

create or replace function public.qcms_supply_inherit_downstream()
returns trigger language plpgsql security definer set search_path=public as $$
declare fr public.supply_forging_receipts%rowtype; ev public.supply_downstream_events%rowtype;
begin
  if new.event_type='MACHINING' then
    if new.source_forging_receipt_id is null then raise exception 'Machining must be linked to a pending Forging Receipt'; end if;
    select * into fr from public.supply_forging_receipts where id=new.source_forging_receipt_id and tenant_id=new.tenant_id;
    if fr.id is null then raise exception 'Linked Forging Receipt is invalid'; end if;
    new.customer_order_id:=fr.customer_order_id;
    new.inward_lot_id:=fr.inward_lot_id;
    new.heat_number:=fr.heat_number;
    new.heat_code:=fr.heat_code;
    new.source_event_id:=null;
  elsif new.event_type in ('FINISHED_GOODS','CUSTOMER_DISPATCH') then
    if new.source_event_id is null then raise exception 'This stage must be linked to the immediately previous Supply Chain stage'; end if;
    select * into ev from public.supply_downstream_events where id=new.source_event_id and tenant_id=new.tenant_id;
    if ev.id is null then raise exception 'Linked previous Supply Chain stage is invalid'; end if;
    if new.event_type='FINISHED_GOODS' and ev.event_type<>'MACHINING' then raise exception 'Finished Goods must be linked to Machining'; end if;
    if new.event_type='CUSTOMER_DISPATCH' and ev.event_type<>'FINISHED_GOODS' then raise exception 'Customer Dispatch must be linked to Finished Goods'; end if;
    new.customer_order_id:=ev.customer_order_id;
    new.inward_lot_id:=ev.inward_lot_id;
    new.heat_number:=ev.heat_number;
    new.heat_code:=ev.heat_code;
    new.source_forging_receipt_id:=null;
  end if;
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_inherit_downstream on public.supply_downstream_events;
create trigger trg_qcms_supply_inherit_downstream
before insert or update of event_type,source_forging_receipt_id,source_event_id,customer_order_id,inward_lot_id,heat_number,heat_code
on public.supply_downstream_events for each row execute function public.qcms_supply_inherit_downstream();

-- -----------------------------------------------------------------------------
-- 3) Case/spacing/punctuation-insensitive Customer Order duplicate guard.
--    Existing engineering natural-key constraints remain active as well.
-- -----------------------------------------------------------------------------
create or replace function public.qcms_normalize_business_text(value text)
returns text language sql immutable set search_path=public as $$
select regexp_replace(lower(coalesce(value,'')),'[^a-z0-9]+','','g');
$$;

create or replace function public.qcms_supply_guard_customer_order_duplicate()
returns trigger language plpgsql security definer set search_path=public as $$
begin
  if new.order_type='PURCHASE_ORDER' and new.status<>'CANCELLED' and exists(
    select 1 from public.supply_customer_orders x
    where x.tenant_id=new.tenant_id and x.customer_id=new.customer_id and x.id<>new.id
      and x.order_type='PURCHASE_ORDER' and x.status<>'CANCELLED'
      and public.qcms_normalize_business_text(coalesce(x.customer_order_no,x.master_reference_no))=public.qcms_normalize_business_text(coalesce(new.customer_order_no,new.master_reference_no))
      and public.qcms_normalize_business_text(x.order_position)=public.qcms_normalize_business_text(new.order_position)
  ) then
    raise exception 'Duplicate Customer Order is not allowed. Customer + Order No. + PosNr already exists (matching punctuation/case ignored).';
  end if;
  return new;
end; $$;
drop trigger if exists trg_qcms_supply_guard_customer_order_duplicate on public.supply_customer_orders;
create trigger trg_qcms_supply_guard_customer_order_duplicate
before insert or update of customer_id,customer_order_no,master_reference_no,order_position,status
on public.supply_customer_orders for each row execute function public.qcms_supply_guard_customer_order_duplicate();

-- -----------------------------------------------------------------------------
-- 4) Material Inward register exposes RMTC date plus Supply Chain link columns.
-- -----------------------------------------------------------------------------
drop view if exists public.v_qsms_inward_register;
create view public.v_qsms_inward_register
with (security_invoker=true) as
select
  i.*,
  p.part_number,
  p.part_name,
  supplier.party_code as supplier_code,
  supplier.party_name as supplier_name,
  r.rmtc_number,
  r.certificate_reference as supplier_rmtc_number,
  r.certificate_date as rmtc_date,
  r.status as rmtc_status,
  r.disposition as rmtc_final_disposition,
  r.certificate_quantity as rmtc_steel_quantity_kg,
  r.normalized_heat_number,
  mill.party_name as steel_mill_name,
  grade.grade_code as material_grade,
  coalesce((
    select d.disposition from public.inspection_reports d
    where d.inward_lot_id=i.id and d.report_type='DIMENSIONAL'
    order by d.decision_at desc nulls last,d.updated_at desc limit 1
  ),'PENDING') as dimensional_report_disposition,
  coalesce((
    select l.disposition from public.lab_tests l
    where l.inward_lot_id=i.id and l.test_type='METLAB'
    order by l.decision_at desc nulls last,l.updated_at desc limit 1
  ),'PENDING') as metlab_report_disposition
from public.inward_lots i
join public.parts p on p.id=i.part_id
join public.parties supplier on supplier.id=i.supplier_id
join public.rmtc_approvals r on r.id=i.rmtc_approval_id
left join public.parties mill on mill.id=r.steel_mill_id
left join public.material_grades grade on grade.id=p.material_grade_id;
grant select on public.v_qsms_inward_register to authenticated;

-- -----------------------------------------------------------------------------
-- 5) Existing password-confirmed delete RPC extended to all Supply Chain tables.
-- -----------------------------------------------------------------------------
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
  'qc_calculation_records','quality_complaints','quality_complaint_followups','quality_complaint_actions',
  'supply_customer_orders','supply_rm_purchase_orders','supply_rm_receipts','supply_rm_dispatches','supply_forging_orders','supply_forging_receipts','supply_downstream_events'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 if p_table_name is null or not (p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table'; end if;
 allowed:=role_name='ADMIN' or exists(
   select 1 from public.user_module_permissions p
   where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_archive
 );
 if not allowed then raise exception 'Delete permission is not assigned for this module'; end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
 get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant'; end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then
 raise exception 'This record is linked to another master or transaction. Delete the linked child record first, or deactivate/cancel the record instead.';
end;
$$;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
