-- QCMS v4.14.49 R36b · Inventory & Stock Reports.
-- Bulk (all parts at once) stage stock using the same formulas as public.qcms_part_stage_stock,
-- plus RM stock by heat, forging stock by supplier and a date-wise stock movement ledger.
-- Re-runnable: create or replace only. Every object is SECURITY INVOKER, so table RLS applies.

create or replace function public.qcms_stock_by_stage(p_part_id uuid default null)
returns table (
  part_id uuid, part_number text, fsi_part_number text, part_name text, customer_name text, material_grade text,
  open_orders bigint, open_order_qty_pcs numeric, pending_order_pcs numeric, rm_required_kg numeric,
  rm_ordered_kg numeric, rm_received_kg numeric, rm_pending_receipt_kg numeric, rm_at_fsi_kg numeric,
  rm_sent_to_forger_kg numeric, rm_consumed_at_forger_kg numeric, rm_at_forger_kg numeric,
  forging_ordered_pcs numeric, forging_received_pcs numeric, forging_rejected_pcs numeric, forging_pending_at_forger_pcs numeric,
  machined_pcs numeric, machining_wip_pcs numeric, machined_pending_fg_pcs numeric, fg_produced_pcs numeric,
  fg_stock_pcs numeric, dispatched_pcs numeric,
  opening_rm_kg numeric, opening_forging_pcs numeric, opening_machining_pcs numeric, opening_fg_pcs numeric,
  last_activity_date date
)
language sql
stable
security invoker
set search_path = public
as $$
  with p as (
    select pt.id, pt.part_number, pt.fsi_part_number, pt.part_name, c.party_name customer_name, g.grade_code
      from public.parts pt
      left join public.material_grades g on g.id = pt.material_grade_id
      left join public.parties c on c.id = pt.customer_id
     where p_part_id is null or pt.id = p_part_id
  ),
  co as (
    select o.part_id,
           count(*) filter (where o.status not in ('COMPLETED', 'CANCELLED')) open_orders,
           coalesce(sum(o.order_qty_pcs) filter (where o.status not in ('COMPLETED', 'CANCELLED')), 0) order_qty,
           coalesce(sum(o.required_rm_kg) filter (where o.status not in ('COMPLETED', 'CANCELLED')), 0) rm_required,
           max(o.order_date) d
      from public.supply_customer_orders o
     where p_part_id is null or o.part_id = p_part_id
     group by o.part_id
  ),
  rmpo as (
    select o.part_id, coalesce(sum(s.ordered_qty_kg), 0) kg, max(s.order_date) d
      from public.supply_rm_purchase_orders s join public.supply_customer_orders o on o.id = s.customer_order_id
     where coalesce(s.status, '') <> 'CANCELLED' and (p_part_id is null or o.part_id = p_part_id)
     group by o.part_id
  ),
  rr as (
    select o.part_id, coalesce(sum(x.received_qty_kg), 0) kg, max(x.receipt_date) d
      from public.supply_rm_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
     where p_part_id is null or o.part_id = p_part_id
     group by o.part_id
  ),
  rd as (
    select o.part_id, coalesce(sum(x.qty_kg), 0) kg, max(x.dispatch_date) d
      from public.supply_rm_dispatches x join public.supply_customer_orders o on o.id = x.customer_order_id
     where p_part_id is null or o.part_id = p_part_id
     group by o.part_id
  ),
  fo as (
    select o.part_id, coalesce(sum(x.order_qty_pcs), 0) pcs, max(x.order_date) d
      from public.supply_forging_orders x join public.supply_customer_orders o on o.id = x.customer_order_id
     where coalesce(x.status, '') <> 'CANCELLED' and (p_part_id is null or o.part_id = p_part_id)
     group by o.part_id
  ),
  fr as (
    select o.part_id, coalesce(sum(x.received_qty_pcs), 0) received, coalesce(sum(x.rejected_qty_pcs), 0) rejected,
           coalesce(sum(coalesce(x.actual_rm_consumed_kg,
                                 (coalesce(x.received_qty_pcs, 0) + coalesce(x.rejected_qty_pcs, 0)) * coalesce(x.gross_weight_kg_snapshot, 0))), 0) consumed_kg,
           max(x.receipt_date) d
      from public.supply_forging_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
     where p_part_id is null or o.part_id = p_part_id
     group by o.part_id
  ),
  ev as (
    select o.part_id,
           coalesce(sum(x.qty_pcs) filter (where x.event_type = 'MACHINING'), 0) machined,
           coalesce(sum(x.qty_pcs) filter (where x.event_type = 'FINISHED_GOODS'), 0) fg,
           coalesce(sum(x.qty_pcs) filter (where x.event_type = 'CUSTOMER_DISPATCH'), 0) dispatched,
           max(x.event_date) d
      from public.supply_downstream_events x join public.supply_customer_orders o on o.id = x.customer_order_id
     where p_part_id is null or o.part_id = p_part_id
     group by o.part_id
  ),
  os_stage as (
    select s.part_id, upper(s.stage) stage,
           round(sum(coalesce(s.available_quantity_pcs, s.quantity_pcs, 0)), 0) pcs,
           round(sum(coalesce(s.quantity_kg, 0)), 3) kg,
           max(s.created_at)::date d
      from public.supply_opening_stock s
     where coalesce(s.status, 'ACTIVE') = 'ACTIVE' and (p_part_id is null or s.part_id = p_part_id)
     group by s.part_id, upper(s.stage)
  ),
  os as (
    select t.part_id,
           coalesce(sum(t.pcs) filter (where t.stage = 'FINISHED_GOODS'), 0) fg,
           coalesce(sum(t.pcs) filter (where t.stage in ('MACHINING', 'OSP_READY', 'AT_OSP', 'FINAL_INSPECTION')), 0) machining,
           coalesce(sum(t.kg) filter (where t.stage = 'RAW_MATERIAL'), 0) rm_kg,
           coalesce(sum(t.pcs) filter (where t.stage in ('FORGING', 'CASTING')), 0) forging,
           max(t.d) d
      from os_stage t group by t.part_id
  )
  select p.id, p.part_number, p.fsi_part_number, p.part_name, p.customer_name, p.grade_code,
         coalesce(co.open_orders, 0),
         round(coalesce(co.order_qty, 0), 0),
         round(greatest(coalesce(co.order_qty, 0) - coalesce(ev.dispatched, 0), 0), 0),
         round(coalesce(co.rm_required, 0), 3),
         round(coalesce(rmpo.kg, 0), 3),
         round(coalesce(rr.kg, 0), 3),
         round(greatest(coalesce(rmpo.kg, 0) - coalesce(rr.kg, 0), 0), 3),
         round(greatest(coalesce(rr.kg, 0) - coalesce(rd.kg, 0), 0) + coalesce(os.rm_kg, 0), 3),
         round(coalesce(rd.kg, 0), 3),
         round(coalesce(fr.consumed_kg, 0), 3),
         round(greatest(coalesce(rd.kg, 0) - coalesce(fr.consumed_kg, 0), 0), 3),
         round(coalesce(fo.pcs, 0), 0),
         round(coalesce(fr.received, 0), 0),
         round(coalesce(fr.rejected, 0), 0),
         round(greatest(coalesce(fo.pcs, 0) - coalesce(fr.received, 0) - coalesce(fr.rejected, 0), 0), 0),
         round(coalesce(ev.machined, 0), 0),
         round(greatest(coalesce(fr.received, 0) + coalesce(os.forging, 0) - coalesce(ev.machined, 0), 0), 0),
         round(greatest(coalesce(ev.machined, 0) + coalesce(os.machining, 0) - coalesce(ev.fg, 0), 0), 0),
         round(coalesce(ev.fg, 0), 0),
         round(greatest(coalesce(ev.fg, 0) + coalesce(os.fg, 0) - coalesce(ev.dispatched, 0), 0), 0),
         round(coalesce(ev.dispatched, 0), 0),
         round(coalesce(os.rm_kg, 0), 3),
         round(coalesce(os.forging, 0), 0),
         round(coalesce(os.machining, 0), 0),
         round(coalesce(os.fg, 0), 0),
         nullif(greatest(coalesce(co.d, '1900-01-01'), coalesce(rmpo.d, '1900-01-01'), coalesce(rr.d, '1900-01-01'), coalesce(rd.d, '1900-01-01'),
                         coalesce(fo.d, '1900-01-01'), coalesce(fr.d, '1900-01-01'), coalesce(ev.d, '1900-01-01'), coalesce(os.d, '1900-01-01')), date '1900-01-01')
    from p
    left join co on co.part_id = p.id
    left join rmpo on rmpo.part_id = p.id
    left join rr on rr.part_id = p.id
    left join rd on rd.part_id = p.id
    left join fo on fo.part_id = p.id
    left join fr on fr.part_id = p.id
    left join ev on ev.part_id = p.id
    left join os on os.part_id = p.id
   order by p.part_number;
$$;

revoke all on function public.qcms_stock_by_stage(uuid) from public, anon;
grant execute on function public.qcms_stock_by_stage(uuid) to authenticated;

-- Report Builder data source: every part, all stages.
create or replace view public.v_qcms_stock_by_stage with (security_invoker = true) as
  select * from public.qcms_stock_by_stage(null);

-- Raw material stock by heat / grade / section (kg): opening + received − dispatched to forger.
create or replace view public.v_qcms_rm_stock_by_heat with (security_invoker = true) as
  with mv as (
    select upper(regexp_replace(coalesce(x.heat_number, ''), '[^A-Za-z0-9]', '', 'g')) heat_key, x.heat_number, x.heat_code,
           o.part_id, coalesce(d.material_grade_id, pt.material_grade_id) grade_id,
           coalesce(nullif(btrim(d.material_section_name), ''), nullif(btrim(d.section_size), ''), pt.section_size) section,
           s.rm_supplier_id supplier_id, x.rmtc_number,
           coalesce(x.received_qty_kg, 0) received_kg, 0::numeric dispatched_kg, 0::numeric opening_kg, x.receipt_date d
      from public.supply_rm_receipts x
      join public.supply_customer_orders o on o.id = x.customer_order_id
      left join public.parts pt on pt.id = o.part_id
      left join public.part_raw_material_details d on d.id = o.raw_material_detail_id
      left join public.supply_rm_purchase_orders s on s.id = x.rm_purchase_order_id
    union all
    select upper(regexp_replace(coalesce(x.heat_number, ''), '[^A-Za-z0-9]', '', 'g')), x.heat_number, x.heat_code,
           o.part_id, coalesce(d.material_grade_id, pt.material_grade_id),
           coalesce(nullif(btrim(d.material_section_name), ''), nullif(btrim(d.section_size), ''), pt.section_size),
           s.rm_supplier_id, r.rmtc_number,
           0, coalesce(x.qty_kg, 0), 0, x.dispatch_date
      from public.supply_rm_dispatches x
      join public.supply_customer_orders o on o.id = x.customer_order_id
      left join public.parts pt on pt.id = o.part_id
      left join public.part_raw_material_details d on d.id = o.raw_material_detail_id
      left join public.supply_rm_receipts r on r.id = x.rm_receipt_id
      left join public.supply_rm_purchase_orders s on s.id = r.rm_purchase_order_id
    union all
    select upper(regexp_replace(coalesce(s.heat_number, ''), '[^A-Za-z0-9]', '', 'g')), s.heat_number, s.heat_code,
           s.part_id, coalesce(s.material_grade_id, d.material_grade_id, pt.material_grade_id),
           coalesce(nullif(btrim(d.material_section_name), ''), nullif(btrim(d.section_size), ''), pt.section_size),
           s.supplier_id, null::text,
           0, 0, coalesce(s.quantity_kg, 0), s.created_at::date
      from public.supply_opening_stock s
      left join public.parts pt on pt.id = s.part_id
      left join public.part_raw_material_details d on d.id = s.raw_material_detail_id
     where upper(s.stage) = 'RAW_MATERIAL' and coalesce(s.status, 'ACTIVE') = 'ACTIVE'
  )
  select coalesce(min(nullif(btrim(mv.heat_number), '')), '(no heat)') heat_number,
         mv.heat_key normalized_heat_number,
         string_agg(distinct nullif(btrim(mv.heat_code), ''), ', ') heat_code,
         g.grade_code material_grade,
         mv.section rm_section,
         string_agg(distinct sp.party_name, ', ') supplier_name,
         coalesce(string_agg(distinct nullif(btrim(mv.rmtc_number), ''), ', '),
                  (select string_agg(distinct a.rmtc_number, ', ') from public.rmtc_approvals a
                    where mv.heat_key <> '' and upper(regexp_replace(coalesce(a.heat_number, ''), '[^A-Za-z0-9]', '', 'g')) = mv.heat_key)) rmtc_number,
         string_agg(distinct pt.part_number, ', ') part_numbers,
         string_agg(distinct pt.fsi_part_number, ', ') fsi_part_numbers,
         round(sum(mv.opening_kg), 3) opening_kg,
         round(sum(mv.received_kg), 3) received_kg,
         round(sum(mv.dispatched_kg), 3) dispatched_kg,
         round(sum(mv.opening_kg + mv.received_kg - mv.dispatched_kg), 3) balance_kg,
         max(mv.d) last_movement_date
    from mv
    left join public.material_grades g on g.id = mv.grade_id
    left join public.parties sp on sp.id = mv.supplier_id
    left join public.parts pt on pt.id = mv.part_id
   group by mv.heat_key, g.grade_code, mv.section;

-- Forging stock at each forging supplier (RM sent, consumed, forgings ordered / received / pending).
create or replace view public.v_qcms_forging_stock_by_supplier with (security_invoker = true) as
  with k as (
    select coalesce(x.forging_supplier_id, o.forging_supplier_id) supplier_id, o.part_id,
           coalesce(x.qty_kg, 0) rm_sent_kg, 0::numeric rm_consumed_kg, 0::numeric ordered_pcs, 0::numeric received_pcs, 0::numeric rejected_pcs, x.dispatch_date d
      from public.supply_rm_dispatches x join public.supply_customer_orders o on o.id = x.customer_order_id
    union all
    select coalesce(x.forging_supplier_id, o.forging_supplier_id), o.part_id, 0, 0, coalesce(x.order_qty_pcs, 0), 0, 0, x.order_date
      from public.supply_forging_orders x join public.supply_customer_orders o on o.id = x.customer_order_id
     where coalesce(x.status, '') <> 'CANCELLED'
    union all
    select coalesce(x.forging_supplier_id, o.forging_supplier_id), o.part_id, 0,
           coalesce(x.actual_rm_consumed_kg, (coalesce(x.received_qty_pcs, 0) + coalesce(x.rejected_qty_pcs, 0)) * coalesce(x.gross_weight_kg_snapshot, 0)),
           0, coalesce(x.received_qty_pcs, 0), coalesce(x.rejected_qty_pcs, 0), x.receipt_date
      from public.supply_forging_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
  )
  select coalesce(sp.party_name, '(not set)') supplier_name, sp.party_code supplier_code,
         pt.part_number, pt.fsi_part_number, pt.part_name, c.party_name customer_name, g.grade_code material_grade,
         round(sum(k.rm_sent_kg), 3) rm_sent_kg,
         round(sum(k.rm_consumed_kg), 3) rm_consumed_kg,
         round(greatest(sum(k.rm_sent_kg) - sum(k.rm_consumed_kg), 0), 3) rm_at_forger_kg,
         round(sum(k.ordered_pcs), 0) forging_ordered_pcs,
         round(sum(k.received_pcs), 0) forging_received_pcs,
         round(sum(k.rejected_pcs), 0) forging_rejected_pcs,
         round(greatest(sum(k.ordered_pcs) - sum(k.received_pcs) - sum(k.rejected_pcs), 0), 0) forging_pending_pcs,
         max(k.d) last_movement_date
    from k
    left join public.parties sp on sp.id = k.supplier_id
    left join public.parts pt on pt.id = k.part_id
    left join public.parties c on c.id = pt.customer_id
    left join public.material_grades g on g.id = pt.material_grade_id
   group by sp.party_name, sp.party_code, pt.part_number, pt.fsi_part_number, pt.part_name, c.party_name, g.grade_code;

-- Date-wise stock movement ledger (receipts / issues) for every part and heat.
create or replace view public.v_qcms_stock_movement_ledger with (security_invoker = true) as
  with m as (
    select s.created_at::date movement_date, 'OPENING STOCK'::text movement_type, upper(s.stage) stage, 'IN'::text direction,
           s.part_id, s.heat_number, coalesce(s.location_party_id, s.supplier_id) party_id, s.lot_reference reference_no, null::uuid customer_order_id,
           coalesce(s.quantity_kg, 0) qty_kg, coalesce(s.available_quantity_pcs, s.quantity_pcs, 0) qty_pcs, s.created_at
      from public.supply_opening_stock s where coalesce(s.status, 'ACTIVE') = 'ACTIVE'
    union all
    select x.receipt_date, 'RM RECEIPT', 'RAW_MATERIAL', 'IN', o.part_id, x.heat_number, po.rm_supplier_id, x.receipt_number, o.id,
           coalesce(x.received_qty_kg, 0), 0, x.created_at
      from public.supply_rm_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
      left join public.supply_rm_purchase_orders po on po.id = x.rm_purchase_order_id
    union all
    select x.dispatch_date, 'RM ISSUE TO FORGER', 'RAW_MATERIAL', 'OUT', o.part_id, x.heat_number, coalesce(x.forging_supplier_id, o.forging_supplier_id),
           coalesce(x.dispatch_number, x.challan_number), o.id, coalesce(x.qty_kg, 0), 0, x.created_at
      from public.supply_rm_dispatches x join public.supply_customer_orders o on o.id = x.customer_order_id
    union all
    select x.receipt_date, 'FORGING RECEIPT', 'FORGING', 'IN', o.part_id, x.heat_number, coalesce(x.forging_supplier_id, o.forging_supplier_id),
           x.receipt_number, o.id, coalesce(x.actual_rm_consumed_kg, 0), coalesce(x.received_qty_pcs, 0), x.created_at
      from public.supply_forging_receipts x join public.supply_customer_orders o on o.id = x.customer_order_id
    union all
    select x.event_date,
           case x.event_type when 'MACHINING' then 'ISSUE TO MACHINING' when 'FINISHED_GOODS' then 'FG RECEIPT' when 'CUSTOMER_DISPATCH' then 'CUSTOMER DISPATCH' else x.event_type end,
           x.event_type, case when x.event_type = 'CUSTOMER_DISPATCH' then 'OUT' else 'TRANSFER' end,
           o.part_id, x.heat_number, case when x.event_type = 'CUSTOMER_DISPATCH' then o.customer_id end,
           coalesce(x.invoice_no, x.reference_no), o.id, 0, coalesce(x.qty_pcs, 0), x.created_at
      from public.supply_downstream_events x join public.supply_customer_orders o on o.id = x.customer_order_id
    union all
    select j.dispatch_date, 'OSP OUT', 'AT_OSP', 'OUT', j.part_id, l.heat_number, j.vendor_id, coalesce(j.osp_job_number, j.dispatch_challan), null::uuid,
           0, coalesce(j.quantity_dispatched, 0), j.created_at
      from public.osp_jobs j left join public.inward_lots l on l.id = j.source_inward_lot_id
    union all
    select r.receipt_date, 'OSP IN', 'AT_OSP', 'IN', j.part_id, l.heat_number, j.vendor_id, coalesce(r.receipt_number, r.receipt_challan), null::uuid,
           0, coalesce(r.quantity_received, 0), r.created_at
      from public.osp_receipts r join public.osp_jobs j on j.id = r.osp_job_id
      left join public.inward_lots l on l.id = j.source_inward_lot_id
    union all
    -- legacy OSP jobs whose receipt was recorded on the job itself (no osp_receipts rows)
    select coalesce(j.receipt_date, j.updated_at::date), 'OSP IN', 'AT_OSP', 'IN', j.part_id, l.heat_number, j.vendor_id, coalesce(j.receipt_number, j.receipt_challan), null::uuid,
           0, coalesce(j.quantity_received, 0), j.updated_at
      from public.osp_jobs j left join public.inward_lots l on l.id = j.source_inward_lot_id
     where coalesce(j.quantity_received, 0) > 0
       and not exists (select 1 from public.osp_receipts r where r.osp_job_id = j.id)
  )
  select m.movement_date, m.movement_type, m.stage, m.direction,
         pt.part_number, pt.fsi_part_number, pt.part_name, c.party_name customer_name, g.grade_code material_grade,
         m.heat_number, pa.party_name party_name, m.reference_no, o.customer_order_no,
         round(m.qty_kg, 3) qty_kg, round(m.qty_pcs, 0) qty_pcs,
         case when m.direction = 'IN' then round(m.qty_kg, 3) else 0 end kg_in,
         case when m.direction = 'OUT' then round(m.qty_kg, 3) else 0 end kg_out,
         case when m.direction = 'IN' then round(m.qty_pcs, 0) else 0 end pcs_in,
         case when m.direction = 'OUT' then round(m.qty_pcs, 0) else 0 end pcs_out,
         m.created_at
    from m
    left join public.parts pt on pt.id = m.part_id
    left join public.parties c on c.id = pt.customer_id
    left join public.material_grades g on g.id = pt.material_grade_id
    left join public.parties pa on pa.id = m.party_id
    left join public.supply_customer_orders o on o.id = m.customer_order_id;

revoke all on public.v_qcms_stock_by_stage, public.v_qcms_rm_stock_by_heat,
              public.v_qcms_forging_stock_by_supplier, public.v_qcms_stock_movement_ledger from anon;
grant select on public.v_qcms_stock_by_stage, public.v_qcms_rm_stock_by_heat,
                public.v_qcms_forging_stock_by_supplier, public.v_qcms_stock_movement_ledger to authenticated;
notify pgrst, 'reload schema';
