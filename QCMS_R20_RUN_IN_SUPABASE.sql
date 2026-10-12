-- QCMS R20 · run once in Supabase → SQL Editor (safe to re-run).
-- 1) One controlled RM Purchase Order may club several Customer Orders of the same supplier.
drop index if exists public.uq_supply_rm_supplier_order_no;
create unique index uq_supply_rm_supplier_order_no
  on public.supply_rm_purchase_orders (tenant_id, rm_supplier_id, lower(supplier_order_no), customer_order_id)
  where (status <> 'CANCELLED');

-- 2) Delete a Purchase Order together with its OWN rows (items, sources, RM/forging stages,
--    confirmations). Real downstream genealogy (receipts, inward, dispatch) still blocks it.
create or replace function public.qcms_delete_purchase_order(p_purchase_order_id uuid)
returns jsonb language plpgsql security definer set search_path to 'public', 'auth' as $fn$
declare
  tid uuid := public.current_tenant_id();
  po public.supply_purchase_orders%rowtype;
  blockers text := '';
  n integer;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission(public.qsms_module_for_table('supply_purchase_orders'), 'archive') then
    raise exception 'Delete/Archive permission is not assigned for Supply Chain';
  end if;
  select * into po from public.supply_purchase_orders where id = p_purchase_order_id and tenant_id = tid for update;
  if po.id is null then raise exception 'Purchase Order not found'; end if;

  select count(*) into n from public.supply_rm_receipts r join public.supply_rm_purchase_orders s on s.id = r.rm_purchase_order_id where s.purchase_order_id = po.id;
  if n > 0 then blockers := blockers || n || ' RM Receipt(s); '; end if;
  select count(*) into n from public.inward_lots i join public.supply_rm_purchase_orders s on s.id = i.supply_rm_purchase_order_id where s.purchase_order_id = po.id;
  if n > 0 then blockers := blockers || n || ' Material Inward(s); '; end if;
  select count(*) into n from public.supply_forging_receipts r join public.supply_forging_orders f on f.id = r.forging_order_id where f.purchase_order_id = po.id;
  if n > 0 then blockers := blockers || n || ' Forging Receipt(s); '; end if;
  select count(*) into n from public.supply_purchase_orders x where x.replaces_purchase_order_id = po.id and x.status <> 'CANCELLED';
  if n > 0 then blockers := blockers || n || ' active replacement PO(s); '; end if;
  if blockers <> '' then
    raise exception 'PO % cannot be deleted - linked transactions: %', po.po_number, blockers;
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

-- 3) Record history ("status window"): who created / changed a record and what changed.
--    Any user who can VIEW the module may read the history of its records.
create or replace function public.qcms_record_history(p_table_name text, p_row_id uuid, p_limit integer default 200)
returns jsonb language plpgsql stable security definer set search_path to 'public', 'auth' as $fn$
declare
  tid uuid := public.current_tenant_id();
  module_name text := public.qsms_module_for_table(p_table_name);
  allowed boolean;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  allowed := public.current_app_role() in ('ADMIN', 'QUALITY_MANAGER')
             or coalesce(public.qcms_effective_module_permission(module_name, 'view'), false);
  if not allowed then raise exception 'View permission is required to see this record history'; end if;
  return coalesce((
    select jsonb_agg(row_to_json(h) order by h.changed_at desc)
    from (
      select a.changed_at, a.operation, a.changed_by,
             coalesce(nullif(p.full_name, ''), p.email, a.changed_by::text, 'System') as changed_by_name,
             p.email as changed_by_email, a.old_data, a.new_data
        from public.audit_log a
        left join public.profiles p on p.id = a.changed_by
       where a.tenant_id = tid and a.table_name = p_table_name and a.row_id = p_row_id
       order by a.changed_at desc
       limit greatest(1, least(coalesce(p_limit, 200), 1000))
    ) h), '[]'::jsonb);
end $fn$;
grant execute on function public.qcms_record_history(text, uuid, integer) to authenticated;
