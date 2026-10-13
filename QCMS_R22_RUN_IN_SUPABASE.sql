-- QCMS R22 · run once in Supabase → SQL Editor (safe to re-run).

-- 1) Price history: periods are controlled per Supplier + Part + Raw Material record + UOM.
--    A new price revision automatically closes the previous open-ended period (end date = new start - 1).
--    Remaining overlaps are explained with the exact dates.
create or replace function public.qcms_guard_part_supplier_price_history()
returns trigger language plpgsql as $fn$
declare p public.parts%rowtype; s public.parties%rowtype; rm public.part_raw_material_details%rowtype; clash record;
begin
  select * into p from public.parts where id=new.part_id;
  if p.id is null then raise exception 'Select a valid Part Number'; end if;
  select * into s from public.parties where id=new.supplier_id;
  if s.id is null then raise exception 'Select a valid Supplier'; end if;
  new.tenant_id:=p.tenant_id;
  if s.tenant_id<>new.tenant_id then raise exception 'Part and Supplier tenant mismatch'; end if;
  if new.raw_material_detail_id is not null then
    select * into rm from public.part_raw_material_details where id=new.raw_material_detail_id;
    if rm.id is null or rm.part_id<>new.part_id or rm.supplier_id<>new.supplier_id then raise exception 'Price history Raw Material record must match the selected Part and Supplier'; end if;
  end if;
  new.currency:=upper(btrim(coalesce(new.currency,'INR')));
  new.uom:=upper(btrim(coalesce(new.uom,'KGS')));
  if new.end_date is not null and new.end_date < new.start_date then
    raise exception 'Price End Date % is before Start Date %', to_char(new.end_date,'DD-MM-YYYY'), to_char(new.start_date,'DD-MM-YYYY');
  end if;
  if tg_op='INSERT' and coalesce(new.status,'ACTIVE')='ACTIVE' then
    update public.part_supplier_price_history h
       set end_date = new.start_date - 1
     where h.tenant_id=new.tenant_id and h.part_id=new.part_id and h.supplier_id=new.supplier_id
       and upper(h.uom)=new.uom and h.status='ACTIVE'
       and coalesce(h.raw_material_detail_id,'00000000-0000-0000-0000-000000000000'::uuid)=coalesce(new.raw_material_detail_id,'00000000-0000-0000-0000-000000000000'::uuid)
       and h.start_date < new.start_date and (h.end_date is null or h.end_date >= new.start_date);
  end if;
  if coalesce(new.status,'ACTIVE')='ACTIVE' then
    select h.start_date, h.end_date, h.price into clash from public.part_supplier_price_history h
     where h.tenant_id=new.tenant_id and h.part_id=new.part_id and h.supplier_id=new.supplier_id
       and upper(h.uom)=new.uom and h.status='ACTIVE' and (new.id is null or h.id<>new.id)
       and coalesce(h.raw_material_detail_id,'00000000-0000-0000-0000-000000000000'::uuid)=coalesce(new.raw_material_detail_id,'00000000-0000-0000-0000-000000000000'::uuid)
       and daterange(h.start_date,coalesce(h.end_date,'infinity'::date),'[]') && daterange(new.start_date,coalesce(new.end_date,'infinity'::date),'[]')
     order by h.start_date limit 1;
    if found then
      raise exception 'Price period % to % overlaps the existing period % to % (price %). Use a Start Date after the existing period, or set an End Date on the existing row first.',
        to_char(new.start_date,'DD-MM-YYYY'), coalesce(to_char(new.end_date,'DD-MM-YYYY'),'open'),
        to_char(clash.start_date,'DD-MM-YYYY'), coalesce(to_char(clash.end_date,'DD-MM-YYYY'),'open'), clash.price;
    end if;
  end if;
  new.updated_at:=now(); new.updated_by:=auth.uid(); return new;
end $fn$;

-- 2) Purchase Order delete: blockers now name the exact documents.
create or replace function public.qcms_delete_purchase_order(p_purchase_order_id uuid)
returns jsonb language plpgsql security definer set search_path to 'public', 'auth' as $fn$
declare
  tid uuid := public.current_tenant_id();
  po public.supply_purchase_orders%rowtype;
  blockers text := '';
  names text;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission(public.qsms_module_for_table('supply_purchase_orders'), 'archive') then
    raise exception 'Delete/Archive permission is not assigned for Supply Chain';
  end if;
  select * into po from public.supply_purchase_orders where id = p_purchase_order_id and tenant_id = tid for update;
  if po.id is null then raise exception 'Purchase Order not found'; end if;

  select string_agg(distinct coalesce(r.receipt_number, left(r.id::text,8)), ', ') into names from public.supply_rm_receipts r join public.supply_rm_purchase_orders s on s.id = r.rm_purchase_order_id where s.purchase_order_id = po.id;
  if names is not null then blockers := blockers || 'RM Receipt ' || names || ' (delete in Supply Chain → RM Receipt); '; end if;
  select string_agg(distinct coalesce(i.inward_number, left(i.id::text,8)), ', ') into names from public.inward_lots i join public.supply_rm_purchase_orders s on s.id = i.supply_rm_purchase_order_id where s.purchase_order_id = po.id;
  if names is not null then blockers := blockers || 'Material Inward ' || names || ' (delete in Inward); '; end if;
  select string_agg(distinct coalesce(r.receipt_number, left(r.id::text,8)), ', ') into names from public.supply_forging_receipts r join public.supply_forging_orders f on f.id = r.forging_order_id where f.purchase_order_id = po.id;
  if names is not null then blockers := blockers || 'Forging Receipt ' || names || ' (delete in Supply Chain → Forging); '; end if;
  select string_agg(x.po_number || ' [' || x.status || ']', ', ') into names from public.supply_purchase_orders x where x.replaces_purchase_order_id = po.id and x.status <> 'CANCELLED';
  if names is not null then blockers := blockers || 'replacement PO ' || names || ' (cancel or delete it first); '; end if;
  if blockers <> '' then
    raise exception 'PO % cannot be deleted. Linked transactions: %', po.po_number, blockers;
  end if;

  update public.part_supplier_price_history set source_purchase_order_item_id = null
   where source_purchase_order_item_id in (select id from public.supply_purchase_order_items where purchase_order_id = po.id);
  update public.supply_purchase_orders set replacement_purchase_order_id = null where replacement_purchase_order_id = po.id;
  update public.supply_purchase_orders set replaces_purchase_order_id = null where replaces_purchase_order_id = po.id;
  delete from public.supply_po_confirmations where purchase_order_id = po.id;
  delete from public.supply_purchase_order_sources where purchase_order_id = po.id;
  delete from public.supply_rm_purchase_orders where purchase_order_id = po.id;
  delete from public.supply_forging_orders where purchase_order_id = po.id;
  delete from public.supply_purchase_order_items where purchase_order_id = po.id;
  delete from public.supply_purchase_orders where id = po.id;
  return jsonb_build_object('deleted', true, 'po_number', po.po_number, 'deleted_by', auth.uid());
end $fn$;
grant execute on function public.qcms_delete_purchase_order(uuid) to authenticated;

-- 3) Customer Order delete: links to CANCELLED POs are released automatically; active POS
--    and real stock movements block the delete with the exact document numbers.
create or replace function public.qcms_delete_customer_order(p_customer_order_id uuid)
returns jsonb language plpgsql security definer set search_path to 'public', 'auth' as $fn$
declare
  tid uuid := public.current_tenant_id();
  co public.supply_customer_orders%rowtype;
  blockers text := '';
  names text;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission(public.qsms_module_for_table('supply_customer_orders'), 'archive') then
    raise exception 'Delete/Archive permission is not assigned for Supply Chain';
  end if;
  select * into co from public.supply_customer_orders where id = p_customer_order_id and tenant_id = tid for update;
  if co.id is null then raise exception 'Customer Order not found'; end if;

  select string_agg(distinct po.po_number || ' [' || replace(po.status,'_',' ') || ']', ', ') into names
    from public.supply_purchase_orders po
   where po.status <> 'CANCELLED' and (
         exists (select 1 from public.supply_purchase_order_sources s where s.purchase_order_id = po.id and s.customer_order_id = co.id)
      or exists (select 1 from public.supply_rm_purchase_orders s where s.purchase_order_id = po.id and s.customer_order_id = co.id)
      or exists (select 1 from public.supply_forging_orders s where s.purchase_order_id = po.id and s.customer_order_id = co.id)
      or exists (select 1 from public.supply_purchase_order_items s where s.purchase_order_id = po.id and s.customer_order_id = co.id));
  if names is not null then blockers := blockers || 'active Purchase Order ' || names || ' (cancel the PO in Purchase Orders, or delete it in Records → Delete Transactions → Purchase Order); '; end if;
  select string_agg(distinct coalesce(s.supplier_order_no, left(s.id::text,8)) || ' [' || s.status || ']', ', ') into names from public.supply_rm_purchase_orders s where s.customer_order_id = co.id and s.purchase_order_id is null and s.status <> 'CANCELLED';
  if names is not null then blockers := blockers || 'RM procurement ' || names || '; '; end if;
  select string_agg(distinct coalesce(s.supplier_order_no, left(s.id::text,8)) || ' [' || s.status || ']', ', ') into names from public.supply_forging_orders s where s.customer_order_id = co.id and s.purchase_order_id is null and s.status <> 'CANCELLED';
  if names is not null then blockers := blockers || 'Forging order ' || names || '; '; end if;
  select string_agg(distinct coalesce(r.receipt_number, left(r.id::text,8)), ', ') into names from public.supply_rm_receipts r where r.customer_order_id = co.id;
  if names is not null then blockers := blockers || 'RM Receipt ' || names || '; '; end if;
  select string_agg(distinct coalesce(r.dispatch_number, left(r.id::text,8)), ', ') into names from public.supply_rm_dispatches r where r.customer_order_id = co.id;
  if names is not null then blockers := blockers || 'RM Dispatch ' || names || '; '; end if;
  select string_agg(distinct coalesce(r.receipt_number, left(r.id::text,8)), ', ') into names from public.supply_forging_receipts r where r.customer_order_id = co.id;
  if names is not null then blockers := blockers || 'Forging Receipt ' || names || '; '; end if;
  select string_agg(distinct coalesce(r.reference_no, r.event_type), ', ') into names from public.supply_downstream_events r where r.customer_order_id = co.id;
  if names is not null then blockers := blockers || 'Downstream event ' || names || '; '; end if;
  select string_agg(distinct coalesce(r.inward_number, left(r.id::text,8)), ', ') into names from public.inward_lots r where r.supply_customer_order_id = co.id;
  if names is not null then blockers := blockers || 'Material Inward ' || names || '; '; end if;
  if blockers <> '' then
    raise exception 'Customer Order % (PO % Pos %) cannot be deleted. Linked transactions: %', co.master_reference_no, coalesce(co.customer_order_no,'-'), coalesce(co.order_position,'-'), blockers;
  end if;

  -- Only CANCELLED-PO links (or cancelled stand-alone stages) remain: release them.
  delete from public.supply_purchase_order_sources s using public.supply_purchase_orders po where s.purchase_order_id = po.id and po.status = 'CANCELLED' and s.customer_order_id = co.id;
  delete from public.supply_rm_purchase_orders s where s.customer_order_id = co.id and (s.status = 'CANCELLED' or s.purchase_order_id in (select id from public.supply_purchase_orders where status = 'CANCELLED'));
  delete from public.supply_forging_orders s where s.customer_order_id = co.id and (s.status = 'CANCELLED' or s.purchase_order_id in (select id from public.supply_purchase_orders where status = 'CANCELLED'));
  update public.supply_purchase_order_items i set customer_order_id = null where i.customer_order_id = co.id and i.purchase_order_id in (select id from public.supply_purchase_orders where status = 'CANCELLED');
  delete from public.supply_customer_orders where id = co.id;
  return jsonb_build_object('deleted', true, 'master_reference_no', co.master_reference_no, 'deleted_by', auth.uid());
end $fn$;
grant execute on function public.qcms_delete_customer_order(uuid) to authenticated;

-- 4) Opening stock at FSI, at a Supplier or at a Vendor (forger / OSP) – raw material, forging or casting.
alter table public.supply_opening_stock add column if not exists stock_location text not null default 'FSI';
alter table public.supply_opening_stock add column if not exists location_party_id uuid references public.parties(id) on delete restrict;
alter table public.supply_opening_stock drop constraint if exists supply_opening_stock_stock_location_check;
alter table public.supply_opening_stock add constraint supply_opening_stock_stock_location_check check (stock_location in ('FSI','SUPPLIER','VENDOR'));
alter table public.supply_opening_stock drop constraint if exists supply_opening_stock_stage_check;
alter table public.supply_opening_stock add constraint supply_opening_stock_stage_check check (stage in ('RAW_MATERIAL','FORGING','CASTING','MACHINING','OSP_READY','AT_OSP','FINAL_INSPECTION','FINISHED_GOODS'));
alter table public.supply_opening_stock drop constraint if exists supply_opening_stock_location_party_check;
alter table public.supply_opening_stock add constraint supply_opening_stock_location_party_check check (stock_location = 'FSI' or location_party_id is not null);

-- 5) Part designation for every Process Flow operation: <FSI Part No>-<Operation No>  (K4404-0, K4404-10, ...)
alter table public.npd_process_flow_steps add column if not exists part_designation text;

create or replace function public.qcms_part_designation_base(p_part_id uuid)
returns text language sql stable as $fn$
  select upper(regexp_replace(coalesce(nullif(btrim(fsi_part_number),''), part_number, ''), '\s+', '', 'g')) from public.parts where id = p_part_id
$fn$;

create or replace function public.qcms_set_step_designation()
returns trigger language plpgsql as $fn$
declare base text;
begin
  select public.qcms_part_designation_base(f.part_id) into base from public.npd_process_flows f where f.id = new.flow_id;
  new.part_designation := case when coalesce(base,'') = '' then null else base || '-' || coalesce(new.operation_no, 0)::text end;
  return new;
end $fn$;
drop trigger if exists trg_qcms_step_designation on public.npd_process_flow_steps;
create trigger trg_qcms_step_designation before insert or update of operation_no, flow_id on public.npd_process_flow_steps
  for each row execute function public.qcms_set_step_designation();

create or replace function public.qcms_refresh_part_designations()
returns trigger language plpgsql as $fn$
begin
  if coalesce(new.fsi_part_number,'') is distinct from coalesce(old.fsi_part_number,'') or new.part_number is distinct from old.part_number then
    update public.npd_process_flow_steps s set part_designation = public.qcms_part_designation_base(new.id) || '-' || coalesce(s.operation_no,0)::text
      from public.npd_process_flows f where f.id = s.flow_id and f.part_id = new.id;
  end if;
  return new;
end $fn$;
drop trigger if exists trg_qcms_part_designations on public.parts;
create trigger trg_qcms_part_designations after update of fsi_part_number, part_number on public.parts
  for each row execute function public.qcms_refresh_part_designations();

update public.npd_process_flow_steps s set part_designation = public.qcms_part_designation_base(f.part_id) || '-' || coalesce(s.operation_no,0)::text
  from public.npd_process_flows f where f.id = s.flow_id and (s.part_designation is null or s.part_designation <> public.qcms_part_designation_base(f.part_id) || '-' || coalesce(s.operation_no,0)::text);

notify pgrst, 'reload schema';
