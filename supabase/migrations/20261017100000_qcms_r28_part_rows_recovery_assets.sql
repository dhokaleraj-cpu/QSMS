-- QCMS R28 · applied automatically by the R28 updater (scripts/apply_sql.py). Safe to re-run.
-- 1) RECOVERY: older QCMS versions saved Part Master grid rows (Raw Material Details, Jominy) with a
--    lookup that did not include the Part, so saving one Part could MOVE another Part's row to it.
--    This re-creates every row a Part lost (from the audit history) if the Part has no equivalent row,
--    re-attaches its supplier technical data and points its price history back to the re-created row.
-- 2) Quality Assets: asset name may repeat (many SNAP GAUGES); Asset Number stays unique.
-- 3) Calibration records for instruments / equipment do not need a Part / Process link.

drop table if exists _qcms_r28_rm_map;
create temporary table _qcms_r28_rm_map (old_id uuid, part_id uuid, new_id uuid);

do $do$
declare rec record; new_id uuid := null; restored integer := 0;
begin
  for rec in
    with moved as (
      select distinct row_id from public.audit_log
       where table_name = 'part_raw_material_details' and operation = 'UPDATE'
         and old_data->>'part_id' is distinct from new_data->>'part_id'),
    snap as (
      select distinct on (a.row_id, a.new_data->>'part_id') a.row_id, (a.new_data->>'part_id')::uuid as part_id, a.new_data as d, a.tenant_id
        from public.audit_log a join moved m on m.row_id = a.row_id
       where a.table_name = 'part_raw_material_details' and a.operation in ('INSERT','UPDATE') and a.new_data->>'part_id' is not null
       order by a.row_id, a.new_data->>'part_id', a.changed_at desc)
    select sn.* from snap sn
     where exists (select 1 from public.parts p where p.id = sn.part_id)
       and not exists (select 1 from public.part_raw_material_details r where r.id = sn.row_id and r.part_id = sn.part_id)
       and not exists (select 1 from public.part_raw_material_details r
                        where r.part_id = sn.part_id and r.supplier_id::text = sn.d->>'supplier_id'
                          and coalesce(r.material_grade_id::text,'') = coalesce(sn.d->>'material_grade_id','')
                          and coalesce(r.material_section_name,'') = coalesce(sn.d->>'material_section_name','')
                          and coalesce(r.section_size,'') = coalesce(sn.d->>'section_size','')
                          and coalesce(r.forging_route,'') = coalesce(sn.d->>'forging_route',''))
  loop
    -- two moved rows can carry the same Part + supplier + grade + section: restore it only once
    select r.id into new_id from public.part_raw_material_details r
     where r.part_id = rec.part_id and r.supplier_id::text = rec.d->>'supplier_id'
       and coalesce(r.material_grade_id::text,'') = coalesce(rec.d->>'material_grade_id','')
       and coalesce(r.material_section_name,'') = coalesce(rec.d->>'material_section_name','')
       and coalesce(r.section_size,'') = coalesce(rec.d->>'section_size','')
       and coalesce(r.forging_route,'') = coalesce(rec.d->>'forging_route','') limit 1;
    if new_id is not null then
      insert into _qcms_r28_rm_map values (rec.row_id, rec.part_id, new_id);
      new_id := null;
      continue;
    end if;
    new_id := gen_random_uuid();
    insert into public.part_raw_material_details (id, tenant_id, part_id, supplier_id, material_grade_id, material_section_name, section_size, forging_route,
           lead_time_days, forging_weight_kg, gross_weight_kg, input_weight_kg, hsn_sac_code, supplier_rm_item_code, supplier_forging_part_number,
           source_part_id, sequence_no, status, remarks)
    values (new_id, rec.tenant_id, rec.part_id, (rec.d->>'supplier_id')::uuid, nullif(rec.d->>'material_grade_id','')::uuid, rec.d->>'material_section_name',
           rec.d->>'section_size', rec.d->>'forging_route', coalesce(nullif(rec.d->>'lead_time_days','')::integer, 0), nullif(rec.d->>'forging_weight_kg','')::numeric,
           nullif(rec.d->>'gross_weight_kg','')::numeric, nullif(rec.d->>'input_weight_kg','')::numeric, rec.d->>'hsn_sac_code', rec.d->>'supplier_rm_item_code',
           rec.d->>'supplier_forging_part_number', nullif(rec.d->>'source_part_id','')::uuid, coalesce(nullif(rec.d->>'sequence_no','')::integer, 10),
           coalesce(rec.d->>'status','ACTIVE'), coalesce(rec.d->>'remarks','') || ' [restored by QCMS R28]');
    insert into _qcms_r28_rm_map values (rec.row_id, rec.part_id, new_id);
    new_id := null;
    restored := restored + 1;
  end loop;
  raise notice 'R28: % raw material row(s) restored', restored;
end $do$;

-- supplier technical data of the restored rows (last known values for that Part)
insert into public.part_raw_material_technical_data (tenant_id, part_id, raw_material_detail_id, supplier_id, heading, value_text, include_on_po, sequence_no, status)
select distinct on (m.new_id, lower(btrim(a.new_data->>'heading'))) a.tenant_id, m.part_id, m.new_id, (select r.supplier_id from public.part_raw_material_details r where r.id = m.new_id), a.new_data->>'heading', coalesce(a.new_data->>'value_text',''),
       coalesce((a.new_data->>'include_on_po')::boolean, true), coalesce(nullif(a.new_data->>'sequence_no','')::integer, 10), coalesce(a.new_data->>'status','ACTIVE')
  from _qcms_r28_rm_map m
  join public.audit_log a on a.table_name = 'part_raw_material_technical_data' and a.operation in ('INSERT','UPDATE')
                         and a.new_data->>'raw_material_detail_id' = m.old_id::text and a.new_data->>'part_id' = m.part_id::text
 where m.old_id <> m.new_id
   and not exists (select 1 from public.part_raw_material_technical_data t where t.raw_material_detail_id = m.new_id and lower(btrim(t.heading)) = lower(btrim(a.new_data->>'heading')))
 order by m.new_id, lower(btrim(a.new_data->>'heading')), a.changed_at desc;

-- price history of that Part pointing at a row now owned by another Part -> point to the restored row
update public.part_supplier_price_history h set raw_material_detail_id = m.new_id
  from _qcms_r28_rm_map m
 where h.part_id = m.part_id and h.raw_material_detail_id = m.old_id and m.old_id <> m.new_id;

-- Jominy requirement rows a Part lost the same way
insert into public.part_jominy_requirements (tenant_id, part_id, jominy_distance_id, distance_label, minimum_hrc, maximum_hrc, sequence_no, status)
select distinct on (a.row_id, a.new_data->>'part_id') a.tenant_id, (a.new_data->>'part_id')::uuid, (a.new_data->>'jominy_distance_id')::uuid,
       a.new_data->>'distance_label', nullif(a.new_data->>'minimum_hrc','')::numeric, nullif(a.new_data->>'maximum_hrc','')::numeric,
       coalesce(nullif(a.new_data->>'sequence_no','')::integer, 10), coalesce(a.new_data->>'status','ACTIVE')
  from public.audit_log a
 where a.table_name = 'part_jominy_requirements' and a.operation in ('INSERT','UPDATE')
   and a.row_id in (select distinct row_id from public.audit_log where table_name = 'part_jominy_requirements' and operation = 'UPDATE'
                     and old_data->>'part_id' is distinct from new_data->>'part_id')
   and exists (select 1 from public.parts p where p.id::text = a.new_data->>'part_id')
   and not exists (select 1 from public.part_jominy_requirements j where j.part_id::text = a.new_data->>'part_id'
                     and (j.jominy_distance_id::text = a.new_data->>'jominy_distance_id' or j.distance_label = a.new_data->>'distance_label'))
 order by a.row_id, a.new_data->>'part_id', a.changed_at desc;

-- 2) Quality Assets: same name allowed, Asset Number unique (already indexed in R21)
do $do$
declare idx record;
begin
  for idx in select indexname from pg_indexes where schemaname = 'public' and tablename = 'quality_assets'
                and indexdef ilike '%unique%' and indexdef ilike '%asset_name%' loop
    execute format('drop index if exists public.%I', idx.indexname);
  end loop;
end $do$;

-- 4) Cancelled Purchase Orders release everything: Customer Orders that only had cancelled
--    PO stages go back to OPEN (they were left IN PROGRESS), now and on every future cancel.
create or replace function public.qcms_r28_release_customer_order(p_order_id uuid)
returns void language sql security definer set search_path to 'public' as $fn$
  update public.supply_customer_orders o set status = 'OPEN', updated_at = now()
   where o.id = p_order_id and o.status = 'IN_PROGRESS'
     and not exists (select 1 from public.supply_rm_purchase_orders r where r.customer_order_id = o.id and r.status <> 'CANCELLED')
     and not exists (select 1 from public.supply_forging_orders f where f.customer_order_id = o.id and f.status <> 'CANCELLED')
     and not exists (select 1 from public.supply_rm_receipts x where x.customer_order_id = o.id)
     and not exists (select 1 from public.supply_rm_dispatches d where d.customer_order_id = o.id)
     and not exists (select 1 from public.supply_forging_receipts fr where fr.customer_order_id = o.id)
     and not exists (select 1 from public.supply_downstream_events e where e.customer_order_id = o.id);
$fn$;
revoke all on function public.qcms_r28_release_customer_order(uuid) from public, anon;
grant execute on function public.qcms_r28_release_customer_order(uuid) to authenticated;

select public.qcms_r28_release_customer_order(o.id) from public.supply_customer_orders o where o.status = 'IN_PROGRESS';

create or replace function public.qcms_r28_release_orders_after_po_cancel()
returns trigger language plpgsql security definer set search_path to 'public' as $fn$
declare oid uuid;
begin
  if new.status = 'CANCELLED' and old.status is distinct from 'CANCELLED' then
    for oid in select distinct customer_order_id from public.supply_purchase_order_sources where purchase_order_id = new.id and customer_order_id is not null
               union select customer_order_id from public.supply_rm_purchase_orders where purchase_order_id = new.id and customer_order_id is not null
               union select customer_order_id from public.supply_forging_orders where purchase_order_id = new.id and customer_order_id is not null loop
      perform public.qcms_r28_release_customer_order(oid);
    end loop;
  end if;
  return new;
end $fn$;
drop trigger if exists trg_qcms_r28_release_orders_after_po_cancel on public.supply_purchase_orders;
create constraint trigger trg_qcms_r28_release_orders_after_po_cancel after update of status on public.supply_purchase_orders
  deferrable initially deferred for each row execute function public.qcms_r28_release_orders_after_po_cancel();

-- 3) Instrument / equipment calibration without a Part / Process link (link_id is already optional)

notify pgrst, 'reload schema';
