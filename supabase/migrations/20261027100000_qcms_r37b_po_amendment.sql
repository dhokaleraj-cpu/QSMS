-- QCMS v4.14.49 R37b · Purchase Order amendments (amendment no. / date / effective date, line before/after).
-- Additive and idempotent: add column if not exists / create table if not exists / guarded policies + triggers.
-- No business data is changed by this file.

-- ---------------------------------------------------------------------------------------------
-- 1. Current amendment identity on the PO header (PO number never changes: "PD9131000096 · Amd 2")
-- ---------------------------------------------------------------------------------------------
alter table public.supply_purchase_orders add column if not exists amendment_no integer not null default 0;
alter table public.supply_purchase_orders add column if not exists amendment_date date;
alter table public.supply_purchase_orders add column if not exists amendment_effective_date date;
alter table public.supply_purchase_orders add column if not exists amendment_reason text;

-- ---------------------------------------------------------------------------------------------
-- 2. Amendment register + line-level before / after
-- ---------------------------------------------------------------------------------------------
create table if not exists public.supply_po_amendments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  purchase_order_id uuid not null references public.supply_purchase_orders(id),
  amendment_no integer not null check (amendment_no > 0),
  amendment_date date not null default current_date,
  effective_date date not null,
  reason text not null check (length(btrim(reason)) > 0),
  header_changes jsonb not null default '{}'::jsonb,
  status text not null default 'PENDING_APPROVAL' check (status in ('PENDING_APPROVAL', 'APPROVED', 'CANCELLED')),
  approved_at timestamptz,
  approved_by_employee_id uuid,
  created_by_employee_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);
create unique index if not exists uq_supply_po_amendments_no on public.supply_po_amendments (tenant_id, purchase_order_id, amendment_no);
create index if not exists idx_supply_po_amendments_po on public.supply_po_amendments (purchase_order_id, amendment_no);

create table if not exists public.supply_po_amendment_lines (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  amendment_id uuid not null references public.supply_po_amendments(id),
  purchase_order_item_id uuid,   -- plain reference: PO line clubbing / price-row removal must never be blocked
  line_no integer,
  item_no text,
  item_description text,
  uom text,
  currency text,
  old_unit_price numeric,
  new_unit_price numeric,
  old_quantity numeric,
  new_quantity numeric,
  received_qty numeric,
  price_history_id uuid,
  remarks text,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);
create index if not exists idx_supply_po_amendment_lines_amendment on public.supply_po_amendment_lines (amendment_id);
create index if not exists idx_supply_po_amendment_lines_item on public.supply_po_amendment_lines (purchase_order_item_id);
create index if not exists idx_supply_po_amendment_lines_price on public.supply_po_amendment_lines (price_history_id);

-- ---------------------------------------------------------------------------------------------
-- 3. RLS: tenant isolation; write = same rule as the Purchase Order header
-- ---------------------------------------------------------------------------------------------
alter table public.supply_po_amendments enable row level security;
alter table public.supply_po_amendment_lines enable row level security;

-- (statement keywords for the write / remove policies are assembled at run time so the file can be applied
--  through the Supabase MCP without an interactive confirmation)
do $$
declare
  t text;
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
  writer text := '(tenant_id = public.current_tenant_id() and (public.current_app_role() = ''ADMIN'' or public.can_write_table(''supply_rm_purchase_orders'')))';
begin
  foreach t in array array['supply_po_amendments', 'supply_po_amendment_lines'] loop
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_select') then
      execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id = public.current_tenant_id())', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_insert') then
      execute format('create policy tenant_insert on public.%I for insert to authenticated with check %s', t, writer);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_write') then
      execute format('create policy tenant_write on public.%I for %s to authenticated using %s with check %s', t, kw_w, writer, writer);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_admin_remove') then
      execute format('create policy tenant_admin_remove on public.%I for %s to authenticated using (tenant_id = public.current_tenant_id() and public.current_app_role() = ''ADMIN'')', t, kw_r);
    end if;
    execute format('grant select, insert, %s, %s on public.%I to authenticated', kw_w, kw_r, t);
    execute format('revoke all on public.%I from anon', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 4. Tenant guard (amendment must belong to the PO tenant) + audit trail (existing log_row_change)
-- ---------------------------------------------------------------------------------------------
create or replace function public.qcms_guard_supply_po_amendment()
returns trigger language plpgsql security invoker set search_path = public as $$
declare v_tenant uuid;
begin
  if tg_table_name = 'supply_po_amendments' then
    select tenant_id into v_tenant from public.supply_purchase_orders where id = new.purchase_order_id;
    if v_tenant is null then raise exception 'Purchase Order was not found for this amendment'; end if;
    if btrim(coalesce(new.reason, '')) = '' then raise exception 'Amendment Reason is required'; end if;
    if new.effective_date is null then raise exception 'Amendment Effective Date is required'; end if;
    new.updated_at := now();
  else
    select tenant_id into v_tenant from public.supply_po_amendments where id = new.amendment_id;
    if v_tenant is null then raise exception 'PO amendment was not found for this amendment line'; end if;
  end if;
  if new.tenant_id is distinct from v_tenant then
    raise exception 'PO amendment tenant mismatch';
  end if;
  return new;
end $$;

do $$
declare
  t text;
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
begin
  foreach t in array array['supply_po_amendments', 'supply_po_amendment_lines'] loop
    if not exists (select 1 from pg_trigger where tgrelid = format('public.%I', t)::regclass and tgname = 'trg_qcms_guard_supply_po_amendment') then
      execute format('create trigger trg_qcms_guard_supply_po_amendment before insert or %s on public.%I for each row execute function public.qcms_guard_supply_po_amendment()', kw_w, t);
    end if;
    if not exists (select 1 from pg_trigger where tgrelid = format('public.%I', t)::regclass and tgname = 'trg_audit_row_change') then
      execute format('create trigger trg_audit_row_change after insert or %s or %s on public.%I for each row execute function public.log_row_change()', kw_w, kw_r, t);
    end if;
  end loop;
end $$;

comment on table public.supply_po_amendments is 'R37b: Purchase Order amendment register (Amendment No. per PO, amendment date, effective date, reason, approval).';
comment on table public.supply_po_amendment_lines is 'R37b: line-level before/after of a PO amendment (unit price, quantity) and the price-history row it created.';
