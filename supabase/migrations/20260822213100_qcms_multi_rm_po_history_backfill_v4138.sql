begin;

-- QCMS v4.13.8 historical compatibility/backfill.
-- Preserve v4.13.7 one-order POs in the new many-source allocation model.
update public.supply_rm_purchase_orders s
set purchase_order_item_id=i.id, updated_at=now()
from public.supply_purchase_order_items i
where s.purchase_order_id=i.purchase_order_id
  and s.customer_order_id=i.customer_order_id
  and s.purchase_order_item_id is null;

insert into public.supply_purchase_order_sources(
  tenant_id,purchase_order_id,purchase_order_item_id,customer_order_id,allocated_qty,allocation_uom
)
select s.tenant_id,s.purchase_order_id,s.purchase_order_item_id,s.customer_order_id,
       greatest(coalesce(s.ordered_qty_kg,0),0.001),'KGS'
from public.supply_rm_purchase_orders s
where s.purchase_order_id is not null
  and s.purchase_order_item_id is not null
  and s.customer_order_id is not null
on conflict(purchase_order_id,customer_order_id) do nothing;

-- Seed supplier / FSI-Part price history from older controlled Purchase Orders.
-- Only actual price changes become new effective periods.
with dated as (
  select distinct on (h.tenant_id,h.supplier_id,i.part_id,upper(coalesce(i.uom,'KGS')),h.order_date)
    h.tenant_id,h.supplier_id,i.part_id,i.raw_material_detail_id,h.order_date,
    coalesce(i.unit_price,0)::numeric as price,
    upper(coalesce(h.currency,'INR')) as currency,
    upper(coalesce(i.uom,'KGS')) as uom,
    i.id as source_item_id,
    i.created_at
  from public.supply_purchase_orders h
  join public.supply_purchase_order_items i on i.purchase_order_id=h.id
  where h.status<>'CANCELLED' and coalesce(i.unit_price,0)>0
  order by h.tenant_id,h.supplier_id,i.part_id,upper(coalesce(i.uom,'KGS')),h.order_date,i.created_at desc
), tagged as (
  select *, lag(price) over(partition by tenant_id,supplier_id,part_id,uom order by order_date,created_at) as prior_price
  from dated
), changes as (
  select * from tagged where prior_price is null or prior_price is distinct from price
), ranged as (
  select *, lead(order_date) over(partition by tenant_id,supplier_id,part_id,uom order by order_date,created_at) as next_start
  from changes
)
insert into public.part_supplier_price_history(
  tenant_id,part_id,supplier_id,raw_material_detail_id,start_date,end_date,price,currency,uom,
  source_purchase_order_item_id,remarks,status
)
select tenant_id,part_id,supplier_id,raw_material_detail_id,order_date,
       case when next_start is null then null else next_start-1 end,
       price,currency,uom,source_item_id,'Backfilled from controlled QCMS Purchase Order history','ACTIVE'
from ranged
on conflict(tenant_id,part_id,supplier_id,upper(uom),start_date) do nothing;

-- Seed Part Master supplier technical rows from the most recent historical PO values when present.
with latest as (
  select distinct on (i.tenant_id,i.part_id,h.supplier_id)
    i.tenant_id,i.part_id,h.supplier_id,i.raw_material_detail_id,
    i.rm_rate_per_kg,i.tool_cost_text,i.profit_percent,i.rejection_icc_text,i.packaging,
    h.order_date,i.created_at
  from public.supply_purchase_order_items i
  join public.supply_purchase_orders h on h.id=i.purchase_order_id
  where i.raw_material_detail_id is not null
  order by i.tenant_id,i.part_id,h.supplier_id,h.order_date desc,i.created_at desc
), rows as (
  select tenant_id,part_id,supplier_id,raw_material_detail_id,heading,value_text,sequence_no from latest
  cross join lateral (values
    ('RM Rate / kg', case when rm_rate_per_kg is null then null else rm_rate_per_kg::text end, 50),
    ('Tool Cost', nullif(tool_cost_text,''), 60),
    ('Profit', case when profit_percent is null then null else profit_percent::text||'%' end, 70),
    ('Rej + ICC', nullif(rejection_icc_text,''), 80),
    ('Packaging', nullif(packaging,''), 90)
  ) v(heading,value_text,sequence_no)
  where value_text is not null and btrim(value_text)<>''
)
insert into public.part_raw_material_technical_data(
  tenant_id,raw_material_detail_id,part_id,supplier_id,heading,value_text,include_on_po,sequence_no,status
)
select tenant_id,raw_material_detail_id,part_id,supplier_id,heading,value_text,true,sequence_no,'ACTIVE'
from rows
on conflict(tenant_id,raw_material_detail_id,lower(btrim(heading))) do nothing;

comment on table public.supply_purchase_order_sources is 'QCMS v4.13.8 allocation map including backfilled v4.13.7 source links; one RM PO may consolidate multiple Customer Orders / Schedules.';

commit;
