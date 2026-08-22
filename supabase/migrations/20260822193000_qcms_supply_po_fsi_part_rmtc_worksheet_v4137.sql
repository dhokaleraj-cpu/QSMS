begin;

-- QCMS v4.13.7
-- Supply purchase orders, FSI confidentiality part number, stock-vs-3-month procurement decision,
-- and generic PO links to existing RM/Forging stage transactions.

-- -----------------------------------------------------------------------------
-- 1) Secondary FSI Part Number for confidentiality-safe external documents.
-- -----------------------------------------------------------------------------
alter table public.parts
  add column if not exists fsi_part_number text;

create unique index if not exists uq_qcms_parts_tenant_fsi_part_number
  on public.parts(tenant_id,lower(btrim(fsi_part_number)))
  where nullif(btrim(fsi_part_number),'') is not null;

comment on column public.parts.fsi_part_number is
  'QCMS v4.13.7: internal FSI Part Number used as the external/vendor-facing identity while preserving the original/customer Part Number inside QCMS.';

-- -----------------------------------------------------------------------------
-- 2) Customer Order demand/stock decision snapshot.
-- -----------------------------------------------------------------------------
alter table public.supply_customer_orders
  add column if not exists rm_procurement_required boolean not null default true,
  add column if not exists available_stock_pcs_snapshot numeric not null default 0,
  add column if not exists three_month_schedule_pcs_snapshot numeric not null default 0,
  add column if not exists procurement_shortage_pcs_snapshot numeric not null default 0,
  add column if not exists procurement_decision text not null default 'REQUIRED';

alter table public.supply_customer_orders
  drop constraint if exists supply_customer_orders_required_rm_kg_check;
alter table public.supply_customer_orders
  add constraint supply_customer_orders_required_rm_kg_check check(required_rm_kg>=0);

alter table public.supply_customer_orders
  drop constraint if exists supply_customer_orders_procurement_decision_check;
alter table public.supply_customer_orders
  add constraint supply_customer_orders_procurement_decision_check
    check(procurement_decision in ('REQUIRED','AVAILABLE_STOCK','MANUAL_NOT_REQUIRED','DIRECT_FORGING'));

alter table public.supply_customer_orders
  drop constraint if exists supply_customer_orders_available_stock_pcs_snapshot_check;
alter table public.supply_customer_orders
  add constraint supply_customer_orders_available_stock_pcs_snapshot_check check(available_stock_pcs_snapshot>=0);
alter table public.supply_customer_orders
  drop constraint if exists supply_customer_orders_three_month_schedule_pcs_snapshot_check;
alter table public.supply_customer_orders
  add constraint supply_customer_orders_three_month_schedule_pcs_snapshot_check check(three_month_schedule_pcs_snapshot>=0);
alter table public.supply_customer_orders
  drop constraint if exists supply_customer_orders_procurement_shortage_pcs_snapshot_check;
alter table public.supply_customer_orders
  add constraint supply_customer_orders_procurement_shortage_pcs_snapshot_check check(procurement_shortage_pcs_snapshot>=0);

comment on column public.supply_customer_orders.rm_procurement_required is
  'QCMS v4.13.7: user-confirmed RM procurement flag after checking available system quantity against the rolling three-month schedule.';

-- -----------------------------------------------------------------------------
-- 3) Controlled Purchase Order header + line item.
--    The stage-specific RM/Forging order tables remain the execution registers.
-- -----------------------------------------------------------------------------
create table if not exists public.supply_purchase_orders(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  po_number text not null,
  po_type text not null check(po_type in ('RAW_MATERIAL','FORGING')),
  supplier_id uuid not null references public.parties(id) on delete restrict,
  order_date date not null default current_date,
  delivery_date date,
  requisitioner text,
  ship_via text,
  incoterm text,
  payment_term text,
  quotation_reference text,
  quotation_date date,
  old_po_reference text,
  currency text not null default 'INR',
  plant_snapshot jsonb not null default '{}'::jsonb,
  vendor_snapshot jsonb not null default '{}'::jsonb,
  ship_to_snapshot jsonb not null default '{}'::jsonb,
  remarks text,
  special_instructions text,
  subtotal numeric not null default 0,
  cgst_amount numeric not null default 0,
  sgst_amount numeric not null default 0,
  igst_amount numeric not null default 0,
  other_amount numeric not null default 0,
  grand_total numeric not null default 0,
  standard_terms_code text not null default 'FSI/703/F04',
  standard_terms_revision text not null default '00',
  standard_terms_date date default date '2023-04-01',
  status text not null default 'OPEN' check(status in ('DRAFT','OPEN','PARTIAL','CLOSED','CANCELLED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(tenant_id,po_number)
);

create table if not exists public.supply_purchase_order_items(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  purchase_order_id uuid not null references public.supply_purchase_orders(id) on delete cascade,
  customer_order_id uuid references public.supply_customer_orders(id) on delete restrict,
  part_id uuid not null references public.parts(id) on delete restrict,
  material_grade_id uuid references public.material_grades(id) on delete restrict,
  item_no text not null,
  fsi_part_number_snapshot text,
  original_part_number_snapshot text,
  item_description text not null,
  rm_section text,
  quantity numeric not null check(quantity>0),
  uom text not null,
  unit_price numeric not null default 0 check(unit_price>=0),
  gst_percent numeric not null default 0 check(gst_percent>=0),
  gst_amount numeric not null default 0 check(gst_amount>=0),
  line_total numeric not null default 0 check(line_total>=0),
  forging_weight_kg numeric,
  gross_weight_kg numeric,
  rm_rate_per_kg numeric,
  tool_cost_text text,
  profit_percent numeric,
  rejection_icc_text text,
  packaging text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create index if not exists idx_qcms_supply_po_type_status on public.supply_purchase_orders(tenant_id,po_type,status,delivery_date);
create index if not exists idx_qcms_supply_po_supplier on public.supply_purchase_orders(tenant_id,supplier_id,order_date);
create index if not exists idx_qcms_supply_po_item_po on public.supply_purchase_order_items(purchase_order_id);
create index if not exists idx_qcms_supply_po_item_part on public.supply_purchase_order_items(tenant_id,part_id);
create index if not exists idx_qcms_supply_po_item_customer_order on public.supply_purchase_order_items(customer_order_id);

alter table public.supply_rm_purchase_orders
  add column if not exists purchase_order_id uuid references public.supply_purchase_orders(id) on delete restrict;
alter table public.supply_forging_orders
  add column if not exists purchase_order_id uuid references public.supply_purchase_orders(id) on delete restrict;
create index if not exists idx_supply_rm_purchase_orders_document on public.supply_rm_purchase_orders(purchase_order_id);
create index if not exists idx_supply_forging_orders_document on public.supply_forging_orders(purchase_order_id);

-- Tenant-scoped PO number sequence. Starts in the same PD900xxx family as the reference PO.
create table if not exists public.supply_po_sequences(
  tenant_id uuid primary key references public.tenants(id) on delete cascade,
  current_value bigint not null default 900000,
  updated_at timestamptz not null default now()
);

create or replace function public.qcms_next_supply_po_number()
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare tid uuid:=public.current_tenant_id(); next_value bigint;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  if not public.can_write_table('supply_rm_purchase_orders') and public.current_app_role()<>'ADMIN' then
    raise exception 'Supply Chain procurement create/edit permission is required';
  end if;
  insert into public.supply_po_sequences(tenant_id,current_value) values(tid,900000)
  on conflict(tenant_id) do nothing;
  update public.supply_po_sequences
     set current_value=current_value+1,updated_at=now()
   where tenant_id=tid
   returning current_value into next_value;
  return 'PD'||lpad(next_value::text,6,'0');
end;
$$;

-- -----------------------------------------------------------------------------
-- 4) Audit + tenant RLS. PO tables inherit Supply Chain write authority.
-- -----------------------------------------------------------------------------
do $$
declare table_name text;
begin
  foreach table_name in array array['supply_purchase_orders','supply_purchase_order_items'] loop
    execute format('alter table public.%I enable row level security',table_name);
    execute format('drop trigger if exists trg_touch_updated_at on public.%I',table_name);
    execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()',table_name);
    execute format('drop trigger if exists trg_audit_row_change on public.%I',table_name);
    execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()',table_name);
    execute format('drop policy if exists tenant_select on public.%I',table_name);
    execute format('drop policy if exists tenant_insert on public.%I',table_name);
    execute format('drop policy if exists tenant_update on public.%I',table_name);
    execute format('drop policy if exists tenant_delete on public.%I',table_name);
    execute format('create policy tenant_select on public.%I for select to authenticated using(tenant_id=public.current_tenant_id())',table_name);
    execute format('create policy tenant_insert on public.%I for insert to authenticated with check(tenant_id=public.current_tenant_id() and (public.current_app_role()=''ADMIN'' or public.can_write_table(''supply_rm_purchase_orders'')))',table_name);
    execute format('create policy tenant_update on public.%I for update to authenticated using(tenant_id=public.current_tenant_id() and (public.current_app_role()=''ADMIN'' or public.can_write_table(''supply_rm_purchase_orders''))) with check(tenant_id=public.current_tenant_id() and (public.current_app_role()=''ADMIN'' or public.can_write_table(''supply_rm_purchase_orders'')))',table_name);
    execute format('create policy tenant_delete on public.%I for delete to authenticated using(tenant_id=public.current_tenant_id() and public.current_app_role()=''ADMIN'')',table_name);
  end loop;
end;
$$;

alter table public.supply_po_sequences enable row level security;
drop policy if exists tenant_select on public.supply_po_sequences;
create policy tenant_select on public.supply_po_sequences for select to authenticated using(tenant_id=public.current_tenant_id());

grant select,insert,update,delete on public.supply_purchase_orders to authenticated;
grant select,insert,update,delete on public.supply_purchase_order_items to authenticated;
grant select on public.supply_po_sequences to authenticated;
revoke all on function public.qcms_next_supply_po_number() from public,anon;
grant execute on function public.qcms_next_supply_po_number() to authenticated;

comment on table public.supply_purchase_orders is 'QCMS v4.13.7 controlled RM/Forging Purchase Order document header modeled on FSI purchase order format.';
comment on table public.supply_purchase_order_items is 'QCMS v4.13.7 purchase order lines; external print uses FSI Part Number snapshot to protect original/customer identity.';
comment on function public.qcms_next_supply_po_number() is 'QCMS v4.13.7 tenant-scoped PD purchase order number.';

commit;
