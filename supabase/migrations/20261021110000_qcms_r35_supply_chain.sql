-- QCMS v4.14.49 R35 · Supply Chain
-- 1. qcms_remove_po_source: remove ONE Customer Order from a Purchase Order (guided way out of a
--    blocked Customer Order delete). Nothing received against it; audited; PO returns to approval.
-- 2. qcms_part_stage_stock: live quantities of one Part at every Supply Chain stage (web + mobile).
-- 3. Indexes for the stage-stock / schedule lookups.
-- Safe to re-run (create or replace / if not exists only). No business data is changed.

create or replace function public.qcms_remove_po_source(p_source_id uuid, p_reason text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'auth'
as $function$
declare
  tid uuid := public.current_tenant_id();
  src public.supply_purchase_order_sources%rowtype;
  po public.supply_purchase_orders%rowtype;
  co public.supply_customer_orders%rowtype;
  received numeric := 0;
  other_sources integer := 0;
  item_left integer := 0;
  reason text := nullif(btrim(coalesce(p_reason, '')), '');
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('SUPPLY_CHAIN', 'edit') then
    raise exception 'Purchase Order edit permission is not assigned to this login (Supply Chain · Edit).';
  end if;
  if reason is null then raise exception 'A reason is mandatory to remove a Customer Order from a Purchase Order.'; end if;

  select * into src from public.supply_purchase_order_sources where id = p_source_id and tenant_id = tid for update;
  if src.id is null then raise exception 'PO source allocation not found.'; end if;
  select * into po from public.supply_purchase_orders where id = src.purchase_order_id and tenant_id = tid for update;
  if po.id is null then raise exception 'Purchase Order not found.'; end if;
  if upper(coalesce(po.status, '')) = 'CANCELLED' then
    raise exception 'PO % is cancelled; its orders are already released.', po.po_number;
  end if;
  select * into co from public.supply_customer_orders where id = src.customer_order_id and tenant_id = tid;

  select coalesce(sum(r.received_qty_kg), 0) into received
    from public.supply_rm_receipts r join public.supply_rm_purchase_orders s on s.id = r.rm_purchase_order_id
   where s.purchase_order_id = po.id and s.customer_order_id = src.customer_order_id
     and (src.purchase_order_item_id is null or s.purchase_order_item_id = src.purchase_order_item_id);
  if received > 0 then
    raise exception 'Customer Order % already has % kg received against PO %. Reverse the RM Receipt / Material Inward link first.',
      coalesce(co.customer_order_no, co.master_reference_no, '-'), round(received, 3), po.po_number;
  end if;
  select coalesce(sum(r.received_qty_pcs), 0) into received
    from public.supply_forging_receipts r join public.supply_forging_orders f on f.id = r.forging_order_id
   where f.purchase_order_id = po.id and f.customer_order_id = src.customer_order_id
     and (src.purchase_order_item_id is null or f.purchase_order_item_id = src.purchase_order_item_id);
  if received > 0 then
    raise exception 'Customer Order % already has % pcs forging received against PO %. Reverse the Forging Receipt first.',
      coalesce(co.customer_order_no, co.master_reference_no, '-'), round(received, 0), po.po_number;
  end if;

  select count(*) into other_sources from public.supply_purchase_order_sources where purchase_order_id = po.id and id <> src.id;
  if other_sources = 0 then
    raise exception 'Customer Order % is the only order on PO %. Cancel or delete the whole PO instead (Purchase Order List).',
      coalesce(co.customer_order_no, co.master_reference_no, '-'), po.po_number;
  end if;

  delete from public.supply_rm_purchase_orders
   where purchase_order_id = po.id and customer_order_id = src.customer_order_id
     and (src.purchase_order_item_id is null or purchase_order_item_id = src.purchase_order_item_id);
  delete from public.supply_forging_orders
   where purchase_order_id = po.id and customer_order_id = src.customer_order_id
     and (src.purchase_order_item_id is null or purchase_order_item_id = src.purchase_order_item_id);
  delete from public.supply_purchase_order_sources where id = src.id;

  if src.purchase_order_item_id is not null then
    select count(*) into item_left from public.supply_purchase_order_sources where purchase_order_item_id = src.purchase_order_item_id;
    if item_left = 0 then
      update public.part_supplier_price_history set source_purchase_order_item_id = null where source_purchase_order_item_id = src.purchase_order_item_id;
      delete from public.supply_purchase_order_items where id = src.purchase_order_item_id;
    else
      update public.supply_purchase_order_items i
         set quantity = round(greatest(coalesce((select sum(allocated_qty) from public.supply_purchase_order_sources s where s.purchase_order_item_id = i.id), 0), 0.001), 3),
             line_total = round(round(greatest(coalesce((select sum(allocated_qty) from public.supply_purchase_order_sources s where s.purchase_order_item_id = i.id), 0), 0.001), 3) * coalesce(i.unit_price, 0), 2),
             updated_at = now()
       where i.id = src.purchase_order_item_id;
      update public.supply_purchase_order_items set gst_amount = round(coalesce(line_total, 0) * coalesce(gst_percent, 0) / 100.0, 2)
       where id = src.purchase_order_item_id;
    end if;
  end if;

  update public.supply_purchase_orders
     set remarks = left(concat_ws(E'\n', nullif(remarks, ''),
                  format('[%s] Customer Order %s removed from this PO: %s', to_char(now(), 'DD-MM-YYYY'), coalesce(co.customer_order_no, co.master_reference_no, '-'), reason)), 4000),
         updated_at = now()
   where id = po.id;

  return jsonb_build_object('removed', true, 'purchase_order_id', po.id, 'po_number', po.po_number,
    'customer_order_id', src.customer_order_id, 'customer_order_no', coalesce(co.customer_order_no, co.master_reference_no),
    'was_approved', upper(coalesce(po.approval_status, '')) = 'APPROVED', 'removed_by', auth.uid());
end
$function$;

revoke all on function public.qcms_remove_po_source(uuid, text) from public, anon;
grant execute on function public.qcms_remove_po_source(uuid, text) to authenticated;


create or replace function public.qcms_part_stage_stock(p_part_id uuid, p_heat_number text default null)
returns jsonb
language plpgsql
stable
security invoker
set search_path to 'public'
as $function$
declare
  heat text := nullif(upper(btrim(coalesce(p_heat_number, ''))), '');
  part_row record;
  r jsonb;
  open_orders integer; order_qty numeric; rm_required numeric;
  rm_ordered numeric; rm_received numeric; rm_dispatched numeric;
  fo_ordered numeric; fo_received numeric; fo_rejected numeric;
  machined numeric; fg numeric; dispatched numeric;
  opening jsonb; opening_fg numeric; opening_machining numeric; opening_rm_kg numeric; opening_forging numeric;
begin
  select p.id, p.part_number, p.fsi_part_number, p.part_name, g.grade_code
    into part_row
    from public.parts p left join public.material_grades g on g.id = p.material_grade_id
   where p.id = p_part_id;
  if part_row.id is null then return jsonb_build_object('error', 'Part not found'); end if;

  select count(*) filter (where o.status not in ('COMPLETED', 'CANCELLED')),
         coalesce(sum(o.order_qty_pcs) filter (where o.status not in ('COMPLETED', 'CANCELLED')), 0),
         coalesce(sum(o.required_rm_kg) filter (where o.status not in ('COMPLETED', 'CANCELLED')), 0)
    into open_orders, order_qty, rm_required
    from public.supply_customer_orders o where o.part_id = p_part_id;

  select coalesce(sum(s.ordered_qty_kg), 0) into rm_ordered
    from public.supply_rm_purchase_orders s join public.supply_customer_orders o on o.id = s.customer_order_id
   where o.part_id = p_part_id and coalesce(s.status, '') <> 'CANCELLED';
  select coalesce(sum(x.received_qty_kg), 0) into rm_received
    from public.supply_rm_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
   where o.part_id = p_part_id and (heat is null or upper(x.heat_number) = heat);
  select coalesce(sum(x.qty_kg), 0) into rm_dispatched
    from public.supply_rm_dispatches x join public.supply_customer_orders o on o.id = x.customer_order_id
   where o.part_id = p_part_id and (heat is null or upper(x.heat_number) = heat);
  select coalesce(sum(x.order_qty_pcs), 0) into fo_ordered
    from public.supply_forging_orders x join public.supply_customer_orders o on o.id = x.customer_order_id
   where o.part_id = p_part_id and coalesce(x.status, '') <> 'CANCELLED' and (heat is null or upper(coalesce(x.heat_number, '')) = heat);
  select coalesce(sum(x.received_qty_pcs), 0), coalesce(sum(x.rejected_qty_pcs), 0) into fo_received, fo_rejected
    from public.supply_forging_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
   where o.part_id = p_part_id and (heat is null or upper(coalesce(x.heat_number, '')) = heat);
  select coalesce(sum(x.qty_pcs) filter (where x.event_type = 'MACHINING'), 0),
         coalesce(sum(x.qty_pcs) filter (where x.event_type = 'FINISHED_GOODS'), 0),
         coalesce(sum(x.qty_pcs) filter (where x.event_type = 'CUSTOMER_DISPATCH'), 0)
    into machined, fg, dispatched
    from public.supply_downstream_events x join public.supply_customer_orders o on o.id = x.customer_order_id
   where o.part_id = p_part_id and (heat is null or upper(coalesce(x.heat_number, '')) = heat);

  select coalesce(jsonb_object_agg(stage, jsonb_build_object('pcs', pcs, 'kg', kg)), '{}'::jsonb),
         coalesce(sum(pcs) filter (where stage = 'FINISHED_GOODS'), 0),
         coalesce(sum(pcs) filter (where stage in ('MACHINING', 'OSP_READY', 'AT_OSP', 'FINAL_INSPECTION')), 0),
         coalesce(sum(kg) filter (where stage = 'RAW_MATERIAL'), 0),
         coalesce(sum(pcs) filter (where stage in ('FORGING', 'CASTING')), 0)
    into opening, opening_fg, opening_machining, opening_rm_kg, opening_forging
    from (select upper(s.stage) stage, round(sum(coalesce(s.available_quantity_pcs, s.quantity_pcs, 0)), 0) pcs, round(sum(coalesce(s.quantity_kg, 0)), 3) kg
            from public.supply_opening_stock s
           where s.part_id = p_part_id and coalesce(s.status, 'ACTIVE') = 'ACTIVE' and (heat is null or upper(coalesce(s.heat_number, '')) = heat)
           group by upper(s.stage)) t;

  r := jsonb_build_object(
    'part_id', part_row.id, 'part_number', part_row.part_number, 'fsi_part_number', part_row.fsi_part_number,
    'part_name', part_row.part_name, 'material_grade', part_row.grade_code, 'heat_number', heat, 'as_of', now(),
    'opening_stock', opening,
    'customer_orders', jsonb_build_object('open_orders', open_orders, 'order_qty_pcs', round(order_qty, 0),
        'dispatched_pcs', round(dispatched, 0), 'pending_pcs', round(greatest(order_qty - dispatched, 0), 0), 'rm_required_kg', round(rm_required, 3)),
    'rm', jsonb_build_object('ordered_kg', round(rm_ordered, 3), 'received_kg', round(rm_received, 3),
        'pending_receipt_kg', round(greatest(rm_ordered - rm_received, 0), 3), 'dispatched_to_forging_kg', round(rm_dispatched, 3),
        'at_fsi_kg', round(greatest(rm_received - rm_dispatched, 0) + opening_rm_kg, 3)),
    'forging', jsonb_build_object('ordered_pcs', round(fo_ordered, 0), 'received_pcs', round(fo_received, 0), 'rejected_pcs', round(fo_rejected, 0),
        'pending_at_forger_pcs', round(greatest(fo_ordered - fo_received - fo_rejected, 0), 0)),
    'production', jsonb_build_object('machined_pcs', round(machined, 0), 'finished_goods_pcs', round(fg, 0), 'dispatched_pcs', round(dispatched, 0),
        'wip_machining_pcs', round(greatest(fo_received + opening_forging - machined, 0), 0),
        'machined_pending_fg_pcs', round(greatest(machined + opening_machining - fg, 0), 0),
        'fg_stock_pcs', round(greatest(fg + opening_fg - dispatched, 0), 0)),
    'available_pcs', round(greatest(fg + opening_fg - dispatched, 0), 0)
  );
  r := r || jsonb_build_object('stages', jsonb_build_array(
    jsonb_build_object('stage', 'Open customer orders', 'qty', r->'customer_orders'->'pending_pcs', 'unit', 'pcs'),
    jsonb_build_object('stage', 'RM ordered', 'qty', r->'rm'->'ordered_kg', 'unit', 'kg'),
    jsonb_build_object('stage', 'RM pending receipt', 'qty', r->'rm'->'pending_receipt_kg', 'unit', 'kg'),
    jsonb_build_object('stage', 'RM at FSI', 'qty', r->'rm'->'at_fsi_kg', 'unit', 'kg'),
    jsonb_build_object('stage', 'RM sent to forger', 'qty', r->'rm'->'dispatched_to_forging_kg', 'unit', 'kg'),
    jsonb_build_object('stage', 'Forging pending at forger', 'qty', r->'forging'->'pending_at_forger_pcs', 'unit', 'pcs'),
    jsonb_build_object('stage', 'Forgings received', 'qty', r->'forging'->'received_pcs', 'unit', 'pcs'),
    jsonb_build_object('stage', 'Machining WIP', 'qty', r->'production'->'wip_machining_pcs', 'unit', 'pcs'),
    jsonb_build_object('stage', 'Machined, pending FG', 'qty', r->'production'->'machined_pending_fg_pcs', 'unit', 'pcs'),
    jsonb_build_object('stage', 'Finished goods stock', 'qty', r->'production'->'fg_stock_pcs', 'unit', 'pcs'),
    jsonb_build_object('stage', 'Dispatched to customer', 'qty', r->'production'->'dispatched_pcs', 'unit', 'pcs')));
  return r;
end
$function$;

revoke all on function public.qcms_part_stage_stock(uuid, text) from public, anon;
grant execute on function public.qcms_part_stage_stock(uuid, text) to authenticated;

create index if not exists idx_supply_customer_orders_part on public.supply_customer_orders (tenant_id, part_id);
create index if not exists idx_supply_customer_orders_schedule on public.supply_customer_orders (tenant_id, customer_id, part_id, schedule_month);
create index if not exists idx_supply_po_sources_customer_order on public.supply_purchase_order_sources (customer_order_id);
create index if not exists idx_supply_rm_po_customer_order on public.supply_rm_purchase_orders (customer_order_id);
create index if not exists idx_supply_forging_orders_customer_order on public.supply_forging_orders (customer_order_id);
create index if not exists idx_supply_downstream_customer_order on public.supply_downstream_events (customer_order_id);
