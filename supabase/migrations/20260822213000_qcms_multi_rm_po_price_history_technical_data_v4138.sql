begin;

-- QCMS v4.13.8
-- Multi-customer-order RM Purchase Orders, supplier/FSI-part price history,
-- and supplier-specific Part Master raw-material technical data snapshots.

-- -----------------------------------------------------------------------------
-- 1) Supplier-specific technical data under Part Master -> Raw Material Details.
-- -----------------------------------------------------------------------------
create table if not exists public.part_raw_material_technical_data(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  raw_material_detail_id uuid not null references public.part_raw_material_details(id) on delete cascade,
  part_id uuid not null references public.parts(id) on delete cascade,
  supplier_id uuid not null references public.parties(id) on delete restrict,
  heading text not null,
  value_text text not null,
  include_on_po boolean not null default true,
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE' check(status in ('ACTIVE','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);
create unique index if not exists uq_qcms_rm_technical_heading
  on public.part_raw_material_technical_data(tenant_id,raw_material_detail_id,lower(btrim(heading)));
create index if not exists idx_qcms_rm_technical_part_supplier
  on public.part_raw_material_technical_data(tenant_id,part_id,supplier_id,status,sequence_no);

comment on table public.part_raw_material_technical_data is
  'QCMS v4.13.8 supplier-specific heading/value technical data from Part Master Raw Material Details; selected rows snapshot automatically to Purchase Orders.';

-- -----------------------------------------------------------------------------
-- 2) Supplier + Part price history. FSI Part Number is derived from Part Master.
-- -----------------------------------------------------------------------------
create table if not exists public.part_supplier_price_history(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  part_id uuid not null references public.parts(id) on delete cascade,
  supplier_id uuid not null references public.parties(id) on delete restrict,
  raw_material_detail_id uuid references public.part_raw_material_details(id) on delete set null,
  start_date date not null,
  end_date date,
  price numeric not null check(price>=0),
  currency text not null default 'INR',
  uom text not null default 'KGS',
  source_purchase_order_item_id uuid references public.supply_purchase_order_items(id) on delete set null,
  remarks text,
  status text not null default 'ACTIVE' check(status in ('ACTIVE','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  check(end_date is null or end_date>=start_date)
);
create unique index if not exists uq_qcms_part_supplier_price_start
  on public.part_supplier_price_history(tenant_id,part_id,supplier_id,upper(uom),start_date);
create index if not exists idx_qcms_part_supplier_price_lookup
  on public.part_supplier_price_history(tenant_id,supplier_id,part_id,start_date desc,end_date);

comment on table public.part_supplier_price_history is
  'QCMS v4.13.8 Start Date / End Date / Price history matched by Supplier + Part (supplier-facing FSI Part Number).';

create or replace function public.qcms_guard_part_supplier_price_history()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare p public.parts%rowtype; s public.parties%rowtype; rm public.part_raw_material_details%rowtype;
begin
  select * into p from public.parts where id=new.part_id;
  if p.id is null then raise exception 'Select a valid Part Number'; end if;
  select * into s from public.parties where id=new.supplier_id;
  if s.id is null then raise exception 'Select a valid Supplier'; end if;
  new.tenant_id:=p.tenant_id;
  if s.tenant_id<>new.tenant_id then raise exception 'Part and Supplier tenant mismatch'; end if;
  if new.raw_material_detail_id is not null then
    select * into rm from public.part_raw_material_details where id=new.raw_material_detail_id;
    if rm.id is null or rm.part_id<>new.part_id or rm.supplier_id<>new.supplier_id then
      raise exception 'Price history Raw Material record must match the selected Part and Supplier';
    end if;
  end if;
  new.currency:=upper(btrim(coalesce(new.currency,'INR')));
  new.uom:=upper(btrim(coalesce(new.uom,'KGS')));
  if exists(
    select 1 from public.part_supplier_price_history h
    where h.tenant_id=new.tenant_id and h.part_id=new.part_id and h.supplier_id=new.supplier_id
      and upper(h.uom)=new.uom and h.status='ACTIVE'
      and (new.id is null or h.id<>new.id)
      and daterange(h.start_date,coalesce(h.end_date,'infinity'::date),'[]') && daterange(new.start_date,coalesce(new.end_date,'infinity'::date),'[]')
  ) then
    raise exception 'Price history periods cannot overlap for the same Supplier, Part and UOM';
  end if;
  new.updated_at:=now(); new.updated_by:=auth.uid();
  return new;
end;
$$;
drop trigger if exists trg_qcms_guard_part_supplier_price_history on public.part_supplier_price_history;
create trigger trg_qcms_guard_part_supplier_price_history
before insert or update on public.part_supplier_price_history
for each row execute function public.qcms_guard_part_supplier_price_history();

-- -----------------------------------------------------------------------------
-- 3) Many-to-many Customer Order / Schedule allocations under one controlled PO.
-- -----------------------------------------------------------------------------
create table if not exists public.supply_purchase_order_sources(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  purchase_order_id uuid not null references public.supply_purchase_orders(id) on delete cascade,
  purchase_order_item_id uuid not null references public.supply_purchase_order_items(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  allocated_qty numeric not null check(allocated_qty>0),
  allocation_uom text not null default 'KGS',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(purchase_order_id,customer_order_id)
);
create index if not exists idx_qcms_supply_po_sources_item on public.supply_purchase_order_sources(purchase_order_item_id);
create index if not exists idx_qcms_supply_po_sources_order on public.supply_purchase_order_sources(tenant_id,customer_order_id);

alter table public.supply_purchase_order_items
  add column if not exists raw_material_detail_id uuid references public.part_raw_material_details(id) on delete set null,
  add column if not exists technical_data_snapshot jsonb not null default '[]'::jsonb,
  add column if not exists price_history_snapshot jsonb not null default '[]'::jsonb;

alter table public.supply_rm_purchase_orders
  add column if not exists purchase_order_item_id uuid references public.supply_purchase_order_items(id) on delete restrict;
create index if not exists idx_qcms_supply_rm_po_item on public.supply_rm_purchase_orders(purchase_order_item_id);

comment on table public.supply_purchase_order_sources is
  'QCMS v4.13.8 allocation map allowing one Raw Material Purchase Order to consolidate multiple Customer Orders / Schedules while preserving inward genealogy.';
comment on column public.supply_purchase_order_items.technical_data_snapshot is
  'QCMS v4.13.8 supplier-specific Part Master Raw Material technical heading/value rows frozen at PO creation.';

-- -----------------------------------------------------------------------------
-- 4) Tenant RLS, audit and grants.
-- -----------------------------------------------------------------------------
do $$
declare table_name text;
begin
  foreach table_name in array array['part_raw_material_technical_data','part_supplier_price_history','supply_purchase_order_sources'] loop
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
  end loop;
end;
$$;

-- Part-Master-managed tables: Part edit rights or Admin.
create policy tenant_insert on public.part_raw_material_technical_data for insert to authenticated
with check(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('parts')));
create policy tenant_update on public.part_raw_material_technical_data for update to authenticated
using(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('parts')))
with check(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('parts')));
create policy tenant_delete on public.part_raw_material_technical_data for delete to authenticated
using(tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

create policy tenant_insert on public.part_supplier_price_history for insert to authenticated
with check(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('parts') or public.can_write_table('supply_rm_purchase_orders')));
create policy tenant_update on public.part_supplier_price_history for update to authenticated
using(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('parts') or public.can_write_table('supply_rm_purchase_orders')))
with check(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('parts') or public.can_write_table('supply_rm_purchase_orders')));
create policy tenant_delete on public.part_supplier_price_history for delete to authenticated
using(tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

-- PO allocation table: Supply Chain create/edit rights or Admin.
create policy tenant_insert on public.supply_purchase_order_sources for insert to authenticated
with check(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('supply_rm_purchase_orders')));
create policy tenant_update on public.supply_purchase_order_sources for update to authenticated
using(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('supply_rm_purchase_orders')))
with check(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('supply_rm_purchase_orders')));
create policy tenant_delete on public.supply_purchase_order_sources for delete to authenticated
using(tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

grant select,insert,update,delete on public.part_raw_material_technical_data to authenticated;
grant select,insert,update,delete on public.part_supplier_price_history to authenticated;
grant select,insert,update,delete on public.supply_purchase_order_sources to authenticated;
revoke all on function public.qcms_guard_part_supplier_price_history() from public,anon;
grant execute on function public.qcms_guard_part_supplier_price_history() to authenticated;

commit;
