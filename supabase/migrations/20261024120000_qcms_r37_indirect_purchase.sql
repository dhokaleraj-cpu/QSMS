-- QCMS v4.14.49 R37 · Indirect Purchase module (separate from the Direct / Supply Chain Purchase Order).
-- Item master + categories, number series, Purchase Requisition, Indirect Purchase Order (multi-level value-based
-- approval through qcms_module_approval_routes module key INDIRECT_PURCHASE), Indirect Inward (GRN), indirect stock
-- ledger with Issue-to-department, in-app notifications and Global Search entries.
-- Re-runnable and additive only: create table if not exists / add column if not exists / create or replace /
-- guarded policies & triggers / insert ... on conflict do nothing. Every table is tenant scoped with RLS.

-- ---------------------------------------------------------------------------------------------------------------
-- 0. Approval routes: optional value threshold per level (Indirect Purchase uses it; other modules ignore it)
alter table public.qcms_module_approval_routes add column if not exists min_amount numeric;

-- ---------------------------------------------------------------------------------------------------------------
-- 1. Permission helper (module key INDIRECT_PURCHASE)
--    Explicit User / Role / Department rows win (public.qcms_effective_module_permission). When nothing is configured
--    for this user, MANAGEMENT, PROCUREMENT and SUPPLY_CHAIN get full rights; every other role can view.
create or replace function public.qcms_indirect_purchase_can(p_permission text)
returns boolean
language plpgsql
stable
security definer
set search_path = public, auth
as $$
declare
  v_perm text := lower(btrim(coalesce(p_permission, '')));
  v_role text := coalesce(public.current_app_role(), 'VIEWER');
  v_tid uuid := public.current_tenant_id();
begin
  if auth.uid() is null or v_tid is null then return false; end if;
  if v_role = 'ADMIN' then return true; end if;
  if public.qcms_effective_module_permission('INDIRECT_PURCHASE', v_perm) then return true; end if;
  if v_perm in ('view', 'create', 'edit', 'validate', 'approve')
     and v_role in ('MANAGEMENT', 'PROCUREMENT', 'SUPPLY_CHAIN')
     and not exists (select 1 from public.user_module_permissions p
                      where p.tenant_id = v_tid and p.profile_id = auth.uid() and upper(p.module_key) = 'INDIRECT_PURCHASE')
     and not exists (select 1 from public.role_module_defaults r
                      where r.tenant_id = v_tid and upper(btrim(r.role)) = v_role and upper(r.module_key) = 'INDIRECT_PURCHASE'
                        and r.status = 'ACTIVE') then
    return true;
  end if;
  return false;
end $$;
revoke all on function public.qcms_indirect_purchase_can(text) from public, anon;
grant execute on function public.qcms_indirect_purchase_can(text) to authenticated;

create or replace function public.qcms_indirect_purchase_can_write()
returns boolean language sql stable security definer set search_path = public, auth as $$
  select public.qcms_indirect_purchase_can('create') or public.qcms_indirect_purchase_can('edit');
$$;
revoke all on function public.qcms_indirect_purchase_can_write() from public, anon;
grant execute on function public.qcms_indirect_purchase_can_write() to authenticated;

-- Role defaults (visible / editable in Admin → Users & Access → Role defaults). Never overwrites an existing row.
insert into public.role_module_defaults (tenant_id, role, module_key, can_view, can_create, can_edit, can_validate, can_approve, can_archive, status)
select t.id, r.role, 'INDIRECT_PURCHASE', true, r.w, r.w, r.w, r.w, r.arc, 'ACTIVE'
  from public.tenants t
 cross join (values ('ADMIN', true, true), ('MANAGEMENT', true, false), ('PROCUREMENT', true, false), ('SUPPLY_CHAIN', true, false),
                    ('BUSINESS_DEVELOPMENT', false, false), ('QUALITY_MANAGER', false, false), ('METLAB_APPROVER', false, false),
                    ('QUALITY_ENGINEER', false, false), ('PRODUCTION', false, false), ('SQA', false, false),
                    ('MASTER_DATA', false, false), ('AUDITOR', false, false), ('VIEWER', false, false)) as r(role, w, arc)
on conflict (tenant_id, role, module_key) do nothing;

-- ---------------------------------------------------------------------------------------------------------------
-- 2. Tables
create table if not exists public.indirect_item_categories (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  category_code text not null,
  category_name text not null,
  description text,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, category_code)
);

create table if not exists public.indirect_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  item_code text not null,
  item_name text not null,
  category text not null default 'OTHERS',
  description text,
  specification text,
  uom text not null default 'NOS',
  hsn_sac text,
  gst_percent numeric not null default 18 check (gst_percent >= 0 and gst_percent <= 100),
  default_supplier_id uuid references public.parties(id),
  last_price numeric,
  last_price_date date,
  last_supplier_id uuid references public.parties(id),
  currency text not null default 'INR',
  is_stock_item boolean not null default true,
  reorder_level numeric,
  min_stock numeric,
  max_stock numeric,
  storage_location text,
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, item_code)
);

create table if not exists public.indirect_number_series (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  series_key text not null,
  prefix text not null,
  include_branch boolean not null default true,
  include_year boolean not null default true,
  year_mode text not null default 'FY' check (year_mode in ('FY', 'CALENDAR')),
  digits integer not null default 4 check (digits between 3 and 8),
  separator text not null default '-',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, series_key)
);

create table if not exists public.indirect_number_counters (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  series_key text not null,
  scope_key text not null,
  current_value bigint not null default 0,
  updated_at timestamptz not null default now(),
  unique (tenant_id, series_key, scope_key)
);

create table if not exists public.indirect_purchase_requisitions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  pr_number text not null,
  pr_date date not null default current_date,
  company_branch_id uuid references public.company_branches(id),
  department text,
  cost_centre text,
  requested_by_employee_id uuid references public.employees(id),
  requested_by_name text,
  required_date date,
  purpose text,
  priority text not null default 'NORMAL',
  status text not null default 'SUBMITTED',
  approver_employee_id uuid references public.employees(id),
  approved_at timestamptz,
  approval_remarks text,
  converted_po_id uuid,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, pr_number)
);

create table if not exists public.indirect_purchase_requisition_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  requisition_id uuid not null references public.indirect_purchase_requisitions(id) on delete cascade,
  line_no integer not null default 1,
  item_id uuid references public.indirect_items(id),
  item_code text,
  item_name text,
  description text,
  uom text,
  quantity numeric not null default 0 check (quantity >= 0),
  estimated_rate numeric,
  required_date date,
  ordered_qty numeric not null default 0,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);

create table if not exists public.indirect_purchase_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  po_number text not null,
  po_date date not null default current_date,
  company_branch_id uuid references public.company_branches(id),
  plant_snapshot jsonb not null default '{}'::jsonb,
  supplier_id uuid references public.parties(id),
  vendor_snapshot jsonb not null default '{}'::jsonb,
  ship_to_source_type text not null default 'BRANCH',
  ship_to_branch_id uuid references public.company_branches(id),
  ship_to_party_id uuid references public.parties(id),
  ship_to_snapshot jsonb not null default '{}'::jsonb,
  department text,
  cost_centre text,
  requisitioner text,
  requisitioner_employee_id uuid references public.employees(id),
  requisition_id uuid references public.indirect_purchase_requisitions(id),
  delivery_date date,
  payment_term text,
  incoterm text,
  ship_via text,
  quotation_reference text,
  quotation_date date,
  currency text not null default 'INR',
  gst_mode text not null default 'INTRA' check (gst_mode in ('INTRA', 'INTER')),
  gross_amount numeric not null default 0,
  discount_amount numeric not null default 0,
  subtotal numeric not null default 0,
  cgst_amount numeric not null default 0,
  sgst_amount numeric not null default 0,
  igst_amount numeric not null default 0,
  freight_amount numeric not null default 0,
  other_amount numeric not null default 0,
  round_off numeric not null default 0,
  grand_total numeric not null default 0,
  amount_in_words text,
  terms text,
  special_instructions text,
  remarks text,
  status text not null default 'DRAFT'
    check (status in ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'PARTIALLY_RECEIVED', 'CLOSED', 'CANCELLED', 'REJECTED')),
  approval_status text not null default 'DRAFT'
    check (approval_status in ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'CANCELLED')),
  approval_level integer,
  submitted_by_employee_id uuid references public.employees(id),
  submitted_at timestamptz,
  approver_employee_id uuid references public.employees(id),
  approved_at timestamptz,
  approval_remarks text,
  rejected_by_employee_id uuid references public.employees(id),
  rejected_at timestamptz,
  cancelled_by_employee_id uuid references public.employees(id),
  cancelled_at timestamptz,
  cancellation_reason text,
  revision_no integer not null default 0,
  print_options jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, po_number)
);

create table if not exists public.indirect_purchase_order_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  purchase_order_id uuid not null references public.indirect_purchase_orders(id) on delete cascade,
  line_no integer not null default 1,
  item_id uuid references public.indirect_items(id),
  item_code text,
  item_name text,
  description text,
  category text,
  hsn_sac text,
  uom text not null default 'NOS',
  quantity numeric not null check (quantity > 0),
  rate numeric not null default 0 check (rate >= 0),
  discount_percent numeric not null default 0 check (discount_percent >= 0 and discount_percent <= 100),
  discount_amount numeric not null default 0,
  taxable_amount numeric not null default 0,
  gst_percent numeric not null default 0,
  gst_amount numeric not null default 0,
  cgst_amount numeric not null default 0,
  sgst_amount numeric not null default 0,
  igst_amount numeric not null default 0,
  line_total numeric not null default 0,
  required_date date,
  requisition_item_id uuid references public.indirect_purchase_requisition_items(id),
  received_qty numeric not null default 0,
  accepted_qty numeric not null default 0,
  rejected_qty numeric not null default 0,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);

create table if not exists public.indirect_po_approval_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  purchase_order_id uuid not null references public.indirect_purchase_orders(id) on delete cascade,
  level_no integer,
  level_name text,
  action text not null,
  employee_id uuid references public.employees(id),
  remarks text,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);

create table if not exists public.indirect_grns (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  grn_number text not null,
  grn_date date not null default current_date,
  grn_type text not null default 'AGAINST_PO' check (grn_type in ('AGAINST_PO', 'WITHOUT_PO')),
  purchase_order_id uuid references public.indirect_purchase_orders(id),
  company_branch_id uuid references public.company_branches(id),
  supplier_id uuid references public.parties(id),
  supplier_name text,
  supplier_invoice_no text,
  supplier_invoice_date date,
  challan_no text,
  challan_date date,
  vehicle_no text,
  payment_mode text not null default 'CREDIT',
  department text,
  cost_centre text,
  storage_location text,
  received_by_employee_id uuid references public.employees(id),
  received_by_name text,
  subtotal numeric not null default 0,
  gst_amount numeric not null default 0,
  grand_total numeric not null default 0,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PENDING_APPROVAL', 'POSTED', 'REJECTED', 'CANCELLED')),
  approval_status text not null default 'NOT_REQUIRED',
  approver_employee_id uuid references public.employees(id),
  approved_at timestamptz,
  approval_remarks text,
  posted_at timestamptz,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, grn_number)
);

create table if not exists public.indirect_grn_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  grn_id uuid not null references public.indirect_grns(id) on delete cascade,
  line_no integer not null default 1,
  po_item_id uuid references public.indirect_purchase_order_items(id),
  item_id uuid references public.indirect_items(id),
  item_code text,
  item_name text,
  description text,
  uom text,
  ordered_qty numeric,
  received_qty numeric not null default 0 check (received_qty >= 0),
  accepted_qty numeric not null default 0 check (accepted_qty >= 0),
  rejected_qty numeric not null default 0 check (rejected_qty >= 0),
  rejection_reason text,
  rate numeric not null default 0,
  gst_percent numeric not null default 0,
  amount numeric not null default 0,
  storage_location text,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);

create table if not exists public.indirect_stock_ledger (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  company_branch_id uuid references public.company_branches(id),
  item_id uuid not null references public.indirect_items(id),
  txn_date date not null default current_date,
  txn_type text not null check (txn_type in ('OPENING', 'GRN', 'ISSUE', 'RETURN', 'ADJUSTMENT')),
  qty_in numeric not null default 0 check (qty_in >= 0),
  qty_out numeric not null default 0 check (qty_out >= 0),
  balance_after numeric not null default 0,
  rate numeric,
  value numeric,
  reference_table text,
  reference_id uuid,
  reference_no text,
  department text,
  cost_centre text,
  issued_to_employee_id uuid references public.employees(id),
  storage_location text,
  remarks text,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);

create index if not exists indirect_items_tenant_status_idx on public.indirect_items (tenant_id, status);
create index if not exists indirect_po_tenant_status_idx on public.indirect_purchase_orders (tenant_id, status, po_date desc);
create index if not exists indirect_po_items_po_idx on public.indirect_purchase_order_items (purchase_order_id);
create index if not exists indirect_pr_items_pr_idx on public.indirect_purchase_requisition_items (requisition_id);
create index if not exists indirect_grns_po_idx on public.indirect_grns (purchase_order_id);
create index if not exists indirect_grn_items_grn_idx on public.indirect_grn_items (grn_id);
create index if not exists indirect_stock_ledger_item_idx on public.indirect_stock_ledger (tenant_id, item_id, company_branch_id, created_at);
create index if not exists indirect_po_approval_log_po_idx on public.indirect_po_approval_log (purchase_order_id);

-- ---------------------------------------------------------------------------------------------------------------
-- 3. RLS + grants
do $$
declare
  t text;
begin
  foreach t in array array['indirect_item_categories', 'indirect_items', 'indirect_number_series', 'indirect_number_counters',
                           'indirect_purchase_requisitions', 'indirect_purchase_requisition_items', 'indirect_purchase_orders',
                           'indirect_purchase_order_items', 'indirect_po_approval_log', 'indirect_grns', 'indirect_grn_items',
                           'indirect_stock_ledger'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select on public.%I to authenticated', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_select') then
      execute format('create policy %I on public.%I for select to authenticated using (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can(''view''))', t || '_select', t);
    end if;
  end loop;

  -- master / transaction tables written by the website (writers = INDIRECT_PURCHASE create or edit)
  foreach t in array array['indirect_item_categories', 'indirect_items', 'indirect_number_series', 'indirect_purchase_orders',
                           'indirect_purchase_order_items', 'indirect_grns', 'indirect_grn_items'] loop
    execute format('grant insert, update on public.%I to authenticated', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_insert') then
      execute format('create policy %I on public.%I for insert to authenticated with check (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can_write())', t || '_insert', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_update') then
      execute format('create policy %I on public.%I for update to authenticated using (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can_write()) with check (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can_write())', t || '_update', t);
    end if;
  end loop;

  -- line tables: lines of a draft / pending document may be replaced
  foreach t in array array['indirect_purchase_order_items', 'indirect_grn_items', 'indirect_purchase_requisition_items'] loop
    execute format('grant delete on public.%I to authenticated', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_delete') then
      execute format('create policy %I on public.%I for delete to authenticated using (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can_write())', t || '_delete', t);
    end if;
  end loop;

  -- headers: only an ADMIN may delete (normal flow cancels)
  foreach t in array array['indirect_item_categories', 'indirect_items', 'indirect_purchase_requisitions', 'indirect_purchase_orders', 'indirect_grns'] loop
    execute format('grant delete on public.%I to authenticated', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_delete') then
      execute format('create policy %I on public.%I for delete to authenticated using (tenant_id = public.current_tenant_id() and public.current_app_role() = ''ADMIN'')', t || '_delete', t);
    end if;
  end loop;
end $$;

-- Requisitions: any user who can view the module may raise one; the raiser may edit their own; writers may update.
grant insert, update on public.indirect_purchase_requisitions, public.indirect_purchase_requisition_items to authenticated;
do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'indirect_purchase_requisitions' and policyname = 'indirect_purchase_requisitions_insert') then
    create policy indirect_purchase_requisitions_insert on public.indirect_purchase_requisitions for insert to authenticated
      with check (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can('view'));
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'indirect_purchase_requisitions' and policyname = 'indirect_purchase_requisitions_update') then
    create policy indirect_purchase_requisitions_update on public.indirect_purchase_requisitions for update to authenticated
      using (tenant_id = public.current_tenant_id() and (public.qcms_indirect_purchase_can_write() or created_by = auth.uid()))
      with check (tenant_id = public.current_tenant_id() and (public.qcms_indirect_purchase_can_write() or created_by = auth.uid()));
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'indirect_purchase_requisition_items' and policyname = 'indirect_purchase_requisition_items_insert') then
    create policy indirect_purchase_requisition_items_insert on public.indirect_purchase_requisition_items for insert to authenticated
      with check (tenant_id = public.current_tenant_id() and public.qcms_indirect_purchase_can('view'));
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'indirect_purchase_requisition_items' and policyname = 'indirect_purchase_requisition_items_update') then
    create policy indirect_purchase_requisition_items_update on public.indirect_purchase_requisition_items for update to authenticated
      using (tenant_id = public.current_tenant_id() and (public.qcms_indirect_purchase_can_write() or created_by = auth.uid()))
      with check (tenant_id = public.current_tenant_id() and (public.qcms_indirect_purchase_can_write() or created_by = auth.uid()));
  end if;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 4. Triggers: updated_at, audit trail, approval guards
do $$
declare
  t text;
begin
  foreach t in array array['indirect_item_categories', 'indirect_items', 'indirect_number_series', 'indirect_purchase_requisitions',
                           'indirect_purchase_requisition_items', 'indirect_purchase_orders', 'indirect_purchase_order_items',
                           'indirect_grns', 'indirect_grn_items'] loop
    if not exists (select 1 from pg_trigger where tgrelid = ('public.' || t)::regclass and tgname = 'trg_touch_updated_at') then
      execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', t);
    end if;
  end loop;
  foreach t in array array['indirect_items', 'indirect_purchase_requisitions', 'indirect_purchase_orders', 'indirect_purchase_order_items',
                           'indirect_grns', 'indirect_grn_items', 'indirect_stock_ledger'] loop
    if not exists (select 1 from pg_trigger where tgrelid = ('public.' || t)::regclass and tgname = 'trg_audit_row_change') then
      execute format('create trigger trg_audit_row_change after insert or delete or update on public.%I for each row execute function public.log_row_change()', t);
    end if;
  end loop;
end $$;

-- Approval / receipt fields change only through the controlled RPCs below (they set qcms.indirect_rpc = on).
create or replace function qcms_private.qcms__trg_indirect_guard()
returns trigger
language plpgsql
set search_path = public, auth
as $$
declare
  v_rpc boolean := coalesce(current_setting('qcms.indirect_rpc', true), '') = 'on';
begin
  if v_rpc then return new; end if;
  if tg_table_name = 'indirect_purchase_orders' then
    if tg_op = 'INSERT' then
      if new.approval_status in ('APPROVED', 'REJECTED') or new.status in ('APPROVED', 'PARTIALLY_RECEIVED', 'CLOSED', 'REJECTED') then
        raise exception 'An Indirect Purchase Order is created as Draft / Pending Approval; approval is recorded by the approver';
      end if;
    elsif (new.approval_status is distinct from old.approval_status and new.approval_status in ('APPROVED', 'REJECTED'))
       or (new.status is distinct from old.status and new.status in ('APPROVED', 'PARTIALLY_RECEIVED', 'CLOSED', 'REJECTED'))
       or new.approver_employee_id is distinct from old.approver_employee_id
       or new.approved_at is distinct from old.approved_at then
      raise exception 'Indirect PO approval / receipt status can only be changed through the approval or inward workflow';
    end if;
  elsif tg_table_name = 'indirect_purchase_order_items' then
    if tg_op = 'INSERT' then
      if coalesce(new.received_qty, 0) <> 0 or coalesce(new.accepted_qty, 0) <> 0 or coalesce(new.rejected_qty, 0) <> 0 then
        raise exception 'Received quantities are posted by Indirect Inward (GRN) only';
      end if;
    elsif new.received_qty is distinct from old.received_qty or new.accepted_qty is distinct from old.accepted_qty
          or new.rejected_qty is distinct from old.rejected_qty then
      raise exception 'Received quantities are posted by Indirect Inward (GRN) only';
    end if;
  elsif tg_table_name = 'indirect_grns' then
    if tg_op = 'INSERT' then
      if new.status in ('POSTED', 'PENDING_APPROVAL', 'REJECTED') or new.approval_status = 'APPROVED' then
        raise exception 'A GRN is saved as Draft and posted through the Indirect Inward workflow';
      end if;
    elsif (new.status is distinct from old.status and new.status in ('POSTED', 'PENDING_APPROVAL', 'REJECTED'))
       or (old.status = 'POSTED' and new.status is distinct from old.status)
       or (new.approval_status is distinct from old.approval_status and new.approval_status in ('APPROVED', 'REJECTED')) then
      raise exception 'GRN posting / approval is recorded through the Indirect Inward workflow only';
    end if;
  end if;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_indirect_guard() from public, anon, authenticated;

do $$
declare
  t text;
begin
  foreach t in array array['indirect_purchase_orders', 'indirect_purchase_order_items', 'indirect_grns'] loop
    if not exists (select 1 from pg_trigger where tgrelid = ('public.' || t)::regclass and tgname = 'trg_qcms_indirect_guard') then
      execute format('create trigger trg_qcms_indirect_guard before insert or update on public.%I for each row execute function qcms_private.qcms__trg_indirect_guard()', t);
    end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 5. Number series: <PREFIX>-<BRANCH>-<YY>-<SEQ>, configurable per tenant in indirect_number_series
create or replace function public.qcms_next_indirect_number(p_series_key text, p_company_branch_id uuid default null)
returns text
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  v_key text := upper(btrim(coalesce(p_series_key, '')));
  v_cfg public.indirect_number_series%rowtype;
  v_branch text := '';
  v_year text := '';
  v_scope text;
  v_next bigint;
  v_parts text[] := '{}';
begin
  if auth.uid() is null or v_tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  if v_key not in ('IPO', 'IGRN', 'IPR', 'IITEM', 'ISS') then raise exception 'Unknown Indirect Purchase number series %', v_key; end if;
  if v_key <> 'IPR' and not public.qcms_indirect_purchase_can_write() then
    raise exception 'Indirect Purchase create / edit permission is required';
  end if;
  if v_key = 'IPR' and not public.qcms_indirect_purchase_can('view') then
    raise exception 'Indirect Purchase permission is required';
  end if;
  select * into v_cfg from public.indirect_number_series where tenant_id = v_tid and upper(series_key) = v_key;
  if v_cfg.id is null then
    v_cfg.prefix := case v_key when 'IITEM' then 'IND' else v_key end;
    v_cfg.include_branch := v_key <> 'IITEM';
    v_cfg.include_year := v_key <> 'IITEM';
    v_cfg.year_mode := 'FY';
    v_cfg.digits := case v_key when 'IITEM' then 5 else 4 end;
    v_cfg.separator := '-';
  end if;
  if v_cfg.include_branch then
    select upper(coalesce(nullif(btrim(b.plant_code), ''), nullif(btrim(b.branch_code), ''), 'HO')) into v_branch
      from public.company_branches b where b.id = p_company_branch_id and b.tenant_id = v_tid;
    v_branch := coalesce(nullif(v_branch, ''), 'HO');
  end if;
  if v_cfg.include_year then
    if v_cfg.year_mode = 'CALENDAR' or extract(month from current_date) >= 4 then
      v_year := to_char(current_date, 'YY');
    else
      v_year := to_char(current_date - interval '1 year', 'YY');
    end if;
  end if;
  v_scope := coalesce(nullif(v_branch, ''), '*') || '|' || coalesce(nullif(v_year, ''), '*');
  insert into public.indirect_number_counters (tenant_id, series_key, scope_key, current_value)
  values (v_tid, v_key, v_scope, 1)
  on conflict (tenant_id, series_key, scope_key)
  do update set current_value = public.indirect_number_counters.current_value + 1, updated_at = now()
  returning current_value into v_next;
  v_parts := array_append(v_parts, v_cfg.prefix);
  if v_branch <> '' then v_parts := array_append(v_parts, v_branch); end if;
  if v_year <> '' then v_parts := array_append(v_parts, v_year); end if;
  v_parts := array_append(v_parts, lpad(v_next::text, greatest(v_cfg.digits, length(v_next::text)), '0'));
  return array_to_string(v_parts, coalesce(v_cfg.separator, '-'));
end $$;
revoke all on function public.qcms_next_indirect_number(text, uuid) from public, anon;
grant execute on function public.qcms_next_indirect_number(text, uuid) to authenticated;

-- ---------------------------------------------------------------------------------------------------------------
-- 6. Approval: route levels by value (min_amount) → Reports-To manager → any different approver
create or replace function public.qcms_indirect_po_approval_target(p_po_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  po public.indirect_purchase_orders%rowtype;
  submitter public.employees%rowtype;
  target public.employees%rowtype;
  v_dept text;
  v_levels integer[];
  v_level integer;
  r record;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  select * into po from public.indirect_purchase_orders where id = p_po_id and tenant_id = v_tid;
  if po.id is null then raise exception 'Indirect Purchase Order not found'; end if;
  if po.submitted_by_employee_id is not null then
    select * into submitter from public.employees where id = po.submitted_by_employee_id and tenant_id = v_tid;
  end if;
  v_dept := lower(btrim(coalesce(nullif(po.department, ''), submitter.department, '')));

  select coalesce(array_agg(distinct x.level_no order by x.level_no), '{}') into v_levels
    from public.qcms_module_approval_routes x
    join public.employees e on e.id = x.employee_id and e.tenant_id = x.tenant_id and e.status = 'ACTIVE'
   where x.tenant_id = v_tid and upper(btrim(x.module_key)) = 'INDIRECT_PURCHASE' and x.status = 'ACTIVE' and x.required
     and coalesce(x.min_amount, 0) <= coalesce(po.grand_total, 0)
     and (nullif(btrim(coalesce(x.department, '')), '') is null or lower(btrim(x.department)) = v_dept);

  if coalesce(array_length(v_levels, 1), 0) > 0 then
    select min(l) into v_level from unnest(v_levels) l where l >= coalesce(po.approval_level, 0);
    v_level := coalesce(v_level, v_levels[array_length(v_levels, 1)]);
    select x.employee_id, x.level_name, x.min_amount, x.department, x.overdue_after_hours into r
      from public.qcms_module_approval_routes x
      join public.employees e on e.id = x.employee_id and e.tenant_id = x.tenant_id and e.status = 'ACTIVE'
     where x.tenant_id = v_tid and upper(btrim(x.module_key)) = 'INDIRECT_PURCHASE' and x.status = 'ACTIVE' and x.required
       and x.level_no = v_level and coalesce(x.min_amount, 0) <= coalesce(po.grand_total, 0)
       and (nullif(btrim(coalesce(x.department, '')), '') is null or lower(btrim(x.department)) = v_dept)
     order by case when nullif(btrim(coalesce(x.department, '')), '') is not null then 0 else 1 end, x.created_at
     limit 1;
    select * into target from public.employees where id = r.employee_id and tenant_id = v_tid;
    return jsonb_build_object(
      'source', 'CONFIGURED_ROUTE', 'employee_id', target.id, 'employee_code', target.employee_code,
      'employee_name', btrim(concat_ws(' ', target.first_name, target.last_name)), 'email', target.email,
      'department', target.department, 'level_no', v_level,
      'level_name', coalesce(nullif(btrim(r.level_name), ''), 'Level ' || v_level || ' Approval'),
      'min_amount', r.min_amount, 'overdue_after_hours', coalesce(r.overdue_after_hours, 24),
      'levels', to_jsonb(v_levels), 'route_department', r.department,
      'submitted_by_employee_id', po.submitted_by_employee_id, 'grand_total', po.grand_total);
  end if;

  if submitter.reports_to_employee_id is not null then
    select * into target from public.employees where id = submitter.reports_to_employee_id and tenant_id = v_tid and status = 'ACTIVE';
    if target.id is not null then
      return jsonb_build_object(
        'source', 'REPORTS_TO', 'employee_id', target.id, 'employee_code', target.employee_code,
        'employee_name', btrim(concat_ws(' ', target.first_name, target.last_name)), 'email', target.email,
        'department', target.department, 'level_no', 1, 'level_name', 'Reports-To Manager Approval',
        'levels', '[1]'::jsonb, 'overdue_after_hours', 24, 'route_department', submitter.department,
        'submitted_by_employee_id', po.submitted_by_employee_id, 'grand_total', po.grand_total);
    end if;
  end if;

  return jsonb_build_object(
    'source', 'PERMISSION_FALLBACK', 'employee_id', null, 'employee_code', null, 'employee_name', null, 'email', null,
    'department', submitter.department, 'level_no', 1,
    'level_name', 'Any different employee with Indirect Purchase Approve permission', 'levels', '[1]'::jsonb,
    'overdue_after_hours', 24, 'route_department', submitter.department,
    'submitted_by_employee_id', po.submitted_by_employee_id, 'grand_total', po.grand_total);
end $$;
revoke all on function public.qcms_indirect_po_approval_target(uuid) from public, anon;
grant execute on function public.qcms_indirect_po_approval_target(uuid) to authenticated;

create or replace function public.qcms_approve_indirect_po(p_po_id uuid, p_remarks text default null)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  v_admin boolean := public.current_app_role() = 'ADMIN';
  po public.indirect_purchase_orders%rowtype;
  v_emp uuid;
  v_target jsonb;
  v_required uuid;
  v_level integer;
  v_next integer;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not (v_admin or public.qcms_indirect_purchase_can('approve')) then
    raise exception 'Indirect Purchase approval permission is required';
  end if;
  v_emp := public.qcms_current_login_employee_id();
  if v_emp is null then raise exception 'Login is not linked to Employee Master'; end if;
  select * into po from public.indirect_purchase_orders where id = p_po_id and tenant_id = v_tid for update;
  if po.id is null then raise exception 'Indirect Purchase Order not found'; end if;
  if po.approval_status <> 'PENDING_APPROVAL' then raise exception 'Only a pending Indirect Purchase Order can be approved'; end if;
  v_target := public.qcms_indirect_po_approval_target(po.id);
  v_required := nullif(v_target ->> 'employee_id', '')::uuid;
  if not v_admin then
    if v_required is not null and v_emp <> v_required then
      raise exception 'This Indirect PO must be approved by % (%)', coalesce(v_target ->> 'employee_name', 'the route approver'), coalesce(v_target ->> 'level_name', 'approval');
    end if;
    if v_required is null and v_emp = po.submitted_by_employee_id then
      raise exception 'Self-approval is not permitted. Another employee with Indirect Purchase Approve permission must approve this PO';
    end if;
  end if;
  v_level := coalesce((v_target ->> 'level_no')::integer, 1);
  if v_target ->> 'source' = 'CONFIGURED_ROUTE' then
    select min(value::integer) into v_next from jsonb_array_elements_text(coalesce(v_target -> 'levels', '[]'::jsonb)) where value::integer > v_level;
  end if;
  insert into public.indirect_po_approval_log (tenant_id, purchase_order_id, level_no, level_name, action, employee_id, remarks)
  values (v_tid, po.id, v_level, v_target ->> 'level_name', 'APPROVED', v_emp, nullif(btrim(coalesce(p_remarks, '')), ''));
  perform set_config('qcms.indirect_rpc', 'on', true);
  if v_next is not null then
    update public.indirect_purchase_orders
       set approval_level = v_next, approval_remarks = nullif(btrim(coalesce(p_remarks, '')), ''), updated_at = now(), updated_by = auth.uid()
     where id = po.id returning * into po;
  else
    update public.indirect_purchase_orders
       set approval_status = 'APPROVED', status = 'APPROVED', approval_level = v_level, approver_employee_id = v_emp, approved_at = now(),
           approval_remarks = nullif(btrim(coalesce(p_remarks, '')), ''), updated_at = now(), updated_by = auth.uid()
     where id = po.id returning * into po;
    -- last purchase price on the item master
    update public.indirect_items i
       set last_price = l.rate, last_price_date = po.po_date, last_supplier_id = po.supplier_id, updated_at = now()
      from public.indirect_purchase_order_items l
     where l.purchase_order_id = po.id and l.item_id = i.id and i.tenant_id = v_tid;
  end if;
  perform set_config('qcms.indirect_rpc', 'off', true);
  return to_jsonb(po) || jsonb_build_object('next_level', v_next, 'approved_level', v_level);
end $$;
revoke all on function public.qcms_approve_indirect_po(uuid, text) from public, anon;
grant execute on function public.qcms_approve_indirect_po(uuid, text) to authenticated;

create or replace function public.qcms_reject_indirect_po(p_po_id uuid, p_remarks text)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  v_admin boolean := public.current_app_role() = 'ADMIN';
  po public.indirect_purchase_orders%rowtype;
  v_emp uuid;
  v_target jsonb;
  v_required uuid;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not (v_admin or public.qcms_indirect_purchase_can('approve')) then
    raise exception 'Indirect Purchase approval permission is required';
  end if;
  if length(btrim(coalesce(p_remarks, ''))) < 3 then raise exception 'Enter the rejection remarks'; end if;
  v_emp := public.qcms_current_login_employee_id();
  if v_emp is null then raise exception 'Login is not linked to Employee Master'; end if;
  select * into po from public.indirect_purchase_orders where id = p_po_id and tenant_id = v_tid for update;
  if po.id is null then raise exception 'Indirect Purchase Order not found'; end if;
  if po.approval_status <> 'PENDING_APPROVAL' then raise exception 'Only a pending Indirect Purchase Order can be rejected'; end if;
  v_target := public.qcms_indirect_po_approval_target(po.id);
  v_required := nullif(v_target ->> 'employee_id', '')::uuid;
  if not v_admin and v_required is not null and v_emp <> v_required then
    raise exception 'This Indirect PO must be decided by % (%)', coalesce(v_target ->> 'employee_name', 'the route approver'), coalesce(v_target ->> 'level_name', 'approval');
  end if;
  insert into public.indirect_po_approval_log (tenant_id, purchase_order_id, level_no, level_name, action, employee_id, remarks)
  values (v_tid, po.id, (v_target ->> 'level_no')::integer, v_target ->> 'level_name', 'REJECTED', v_emp, btrim(p_remarks));
  perform set_config('qcms.indirect_rpc', 'on', true);
  update public.indirect_purchase_orders
     set approval_status = 'REJECTED', status = 'REJECTED', rejected_by_employee_id = v_emp, rejected_at = now(),
         approval_remarks = btrim(p_remarks), updated_at = now(), updated_by = auth.uid()
   where id = po.id returning * into po;
  perform set_config('qcms.indirect_rpc', 'off', true);
  return to_jsonb(po);
end $$;
revoke all on function public.qcms_reject_indirect_po(uuid, text) from public, anon;
grant execute on function public.qcms_reject_indirect_po(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------------------------------------------
-- 7. Stock ledger (running balance per item + branch; writes only through these functions)
create or replace function qcms_private.qcms__indirect_ledger(
  p_tenant_id uuid, p_branch_id uuid, p_item_id uuid, p_date date, p_type text, p_qty_in numeric, p_qty_out numeric,
  p_rate numeric, p_ref_table text, p_ref_id uuid, p_ref_no text, p_department text, p_cost_centre text,
  p_employee_id uuid, p_location text, p_remarks text)
returns uuid
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_balance numeric;
  v_id uuid;
begin
  perform pg_advisory_xact_lock(hashtext('qcms_indirect_stock:' || p_tenant_id::text || ':' || p_item_id::text || ':' || coalesce(p_branch_id::text, '-')));
  select coalesce(sum(qty_in - qty_out), 0) into v_balance from public.indirect_stock_ledger
   where tenant_id = p_tenant_id and item_id = p_item_id and company_branch_id is not distinct from p_branch_id;
  if coalesce(p_qty_out, 0) > 0 and v_balance - p_qty_out < -0.0005 then
    raise exception 'Insufficient stock: available %, requested %', round(v_balance, 3), round(p_qty_out, 3);
  end if;
  insert into public.indirect_stock_ledger (tenant_id, company_branch_id, item_id, txn_date, txn_type, qty_in, qty_out, balance_after, rate, value,
                                            reference_table, reference_id, reference_no, department, cost_centre, issued_to_employee_id,
                                            storage_location, remarks)
  values (p_tenant_id, p_branch_id, p_item_id, coalesce(p_date, current_date), p_type, coalesce(p_qty_in, 0), coalesce(p_qty_out, 0),
          round(v_balance + coalesce(p_qty_in, 0) - coalesce(p_qty_out, 0), 4), p_rate,
          round((coalesce(p_qty_in, 0) + coalesce(p_qty_out, 0)) * coalesce(p_rate, 0), 2),
          p_ref_table, p_ref_id, p_ref_no, p_department, p_cost_centre, p_employee_id, p_location, p_remarks)
  returning id into v_id;
  return v_id;
end $$;
revoke all on function qcms_private.qcms__indirect_ledger(uuid, uuid, uuid, date, text, numeric, numeric, numeric, text, uuid, text, text, text, uuid, text, text) from public, anon, authenticated;

create or replace function qcms_private.qcms__indirect_grn_to_stock(p_grn_id uuid)
returns integer
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  g public.indirect_grns%rowtype;
  l record;
  n integer := 0;
begin
  select * into g from public.indirect_grns where id = p_grn_id;
  for l in
    select gi.*, coalesce(i.is_stock_item, false) stock_item
      from public.indirect_grn_items gi join public.indirect_items i on i.id = gi.item_id
     where gi.grn_id = g.id and coalesce(gi.accepted_qty, 0) > 0
  loop
    if l.stock_item then
      perform qcms_private.qcms__indirect_ledger(g.tenant_id, g.company_branch_id, l.item_id, g.grn_date, 'GRN', l.accepted_qty, 0, l.rate,
        'indirect_grns', g.id, g.grn_number, g.department, g.cost_centre, null, coalesce(l.storage_location, g.storage_location),
        'Received from ' || coalesce(g.supplier_name, 'supplier'));
      n := n + 1;
    end if;
  end loop;
  return n;
end $$;
revoke all on function qcms_private.qcms__indirect_grn_to_stock(uuid) from public, anon, authenticated;

create or replace function public.qcms_post_indirect_grn(p_grn_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  g public.indirect_grns%rowtype;
  po public.indirect_purchase_orders%rowtype;
  l record;
  poi public.indirect_purchase_order_items%rowtype;
  v_status text;
  v_lines integer := 0;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_indirect_purchase_can_write() then raise exception 'Indirect Purchase create / edit permission is required'; end if;
  select * into g from public.indirect_grns where id = p_grn_id and tenant_id = v_tid for update;
  if g.id is null then raise exception 'GRN not found'; end if;
  if g.status <> 'DRAFT' then raise exception 'GRN % is already %', g.grn_number, g.status; end if;
  for l in select * from public.indirect_grn_items where grn_id = g.id loop
    v_lines := v_lines + 1;
    if abs(coalesce(l.accepted_qty, 0) + coalesce(l.rejected_qty, 0) - coalesce(l.received_qty, 0)) > 0.0005 then
      raise exception 'Line %: accepted + rejected must equal received quantity', l.line_no;
    end if;
    if coalesce(l.rejected_qty, 0) > 0 and length(btrim(coalesce(l.rejection_reason, ''))) = 0 then
      raise exception 'Line %: enter the rejection reason', l.line_no;
    end if;
  end loop;
  if v_lines = 0 then raise exception 'The GRN has no lines'; end if;

  perform set_config('qcms.indirect_rpc', 'on', true);
  if g.grn_type = 'WITHOUT_PO' then
    update public.indirect_grns set status = 'PENDING_APPROVAL', approval_status = 'PENDING_APPROVAL', updated_at = now(), updated_by = auth.uid()
     where id = g.id returning * into g;
    perform set_config('qcms.indirect_rpc', 'off', true);
    return to_jsonb(g);
  end if;

  select * into po from public.indirect_purchase_orders where id = g.purchase_order_id and tenant_id = v_tid for update;
  if po.id is null then raise exception 'The GRN is not linked to an Indirect Purchase Order'; end if;
  if po.approval_status <> 'APPROVED' or po.status not in ('APPROVED', 'PARTIALLY_RECEIVED') then
    raise exception 'Indirect PO % is % – only an approved, open PO can be received', po.po_number, po.status;
  end if;
  for l in select * from public.indirect_grn_items where grn_id = g.id order by line_no loop
    if l.po_item_id is null then raise exception 'Line %: PO line is missing', l.line_no; end if;
    select * into poi from public.indirect_purchase_order_items where id = l.po_item_id and purchase_order_id = po.id for update;
    if poi.id is null then raise exception 'Line %: PO line does not belong to %', l.line_no, po.po_number; end if;
    if coalesce(l.received_qty, 0) > poi.quantity - poi.accepted_qty + 0.0005 then
      raise exception 'Line % (%): received % exceeds pending % %', l.line_no, coalesce(poi.item_code, poi.item_name),
        round(l.received_qty, 3), round(poi.quantity - poi.accepted_qty, 3), poi.uom;
    end if;
    update public.indirect_purchase_order_items
       set received_qty = received_qty + coalesce(l.received_qty, 0), accepted_qty = accepted_qty + coalesce(l.accepted_qty, 0),
           rejected_qty = rejected_qty + coalesce(l.rejected_qty, 0), updated_at = now(), updated_by = auth.uid()
     where id = poi.id;
  end loop;
  select case when bool_and(accepted_qty + 0.0005 >= quantity) then 'CLOSED'
              when bool_or(received_qty > 0) then 'PARTIALLY_RECEIVED' else po.status end
    into v_status from public.indirect_purchase_order_items where purchase_order_id = po.id;
  update public.indirect_purchase_orders set status = v_status, updated_at = now(), updated_by = auth.uid() where id = po.id;
  perform qcms_private.qcms__indirect_grn_to_stock(g.id);
  update public.indirect_grns set status = 'POSTED', posted_at = now(), updated_at = now(), updated_by = auth.uid()
   where id = g.id returning * into g;
  perform set_config('qcms.indirect_rpc', 'off', true);
  return to_jsonb(g) || jsonb_build_object('po_status', v_status);
end $$;
revoke all on function public.qcms_post_indirect_grn(uuid) from public, anon;
grant execute on function public.qcms_post_indirect_grn(uuid) to authenticated;

create or replace function public.qcms_decide_indirect_grn(p_grn_id uuid, p_approve boolean, p_remarks text default null)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  v_admin boolean := public.current_app_role() = 'ADMIN';
  g public.indirect_grns%rowtype;
  v_emp uuid;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not (v_admin or public.qcms_indirect_purchase_can('approve')) then raise exception 'Indirect Purchase approval permission is required'; end if;
  v_emp := public.qcms_current_login_employee_id();
  if v_emp is null and not v_admin then raise exception 'Login is not linked to Employee Master'; end if;
  select * into g from public.indirect_grns where id = p_grn_id and tenant_id = v_tid for update;
  if g.id is null then raise exception 'GRN not found'; end if;
  if g.status <> 'PENDING_APPROVAL' then raise exception 'Only a GRN pending approval can be decided'; end if;
  if not v_admin and (g.created_by = auth.uid() or g.received_by_employee_id = v_emp) then
    raise exception 'Self-approval is not permitted. Another employee with Indirect Purchase Approve permission must decide this GRN';
  end if;
  if not p_approve and length(btrim(coalesce(p_remarks, ''))) < 3 then raise exception 'Enter the rejection remarks'; end if;
  perform set_config('qcms.indirect_rpc', 'on', true);
  if p_approve then
    perform qcms_private.qcms__indirect_grn_to_stock(g.id);
    update public.indirect_grns set status = 'POSTED', approval_status = 'APPROVED', approver_employee_id = v_emp, approved_at = now(),
           approval_remarks = nullif(btrim(coalesce(p_remarks, '')), ''), posted_at = now(), updated_at = now(), updated_by = auth.uid()
     where id = g.id returning * into g;
  else
    update public.indirect_grns set status = 'REJECTED', approval_status = 'REJECTED', approver_employee_id = v_emp, approved_at = now(),
           approval_remarks = btrim(p_remarks), updated_at = now(), updated_by = auth.uid()
     where id = g.id returning * into g;
  end if;
  perform set_config('qcms.indirect_rpc', 'off', true);
  return to_jsonb(g);
end $$;
revoke all on function public.qcms_decide_indirect_grn(uuid, boolean, text) from public, anon;
grant execute on function public.qcms_decide_indirect_grn(uuid, boolean, text) to authenticated;

create or replace function public.qcms_issue_indirect_stock(
  p_item_id uuid, p_qty numeric, p_company_branch_id uuid default null, p_department text default null, p_cost_centre text default null,
  p_issued_to_employee_id uuid default null, p_issue_date date default null, p_remarks text default null, p_txn_type text default 'ISSUE')
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  v_item public.indirect_items%rowtype;
  v_type text := upper(coalesce(nullif(btrim(p_txn_type), ''), 'ISSUE'));
  v_no text;
  v_id uuid;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_indirect_purchase_can_write() then raise exception 'Indirect Purchase create / edit permission is required'; end if;
  if v_type not in ('ISSUE', 'RETURN', 'OPENING', 'ADJUSTMENT') then raise exception 'Unknown stock transaction %', v_type; end if;
  if coalesce(p_qty, 0) = 0 or (v_type <> 'ADJUSTMENT' and p_qty < 0) then raise exception 'Enter a quantity greater than zero'; end if;
  if v_type = 'ISSUE' and length(btrim(coalesce(p_department, ''))) = 0 then raise exception 'Select the department the stock is issued to'; end if;
  select * into v_item from public.indirect_items where id = p_item_id and tenant_id = v_tid;
  if v_item.id is null then raise exception 'Indirect item not found'; end if;
  v_no := public.qcms_next_indirect_number('ISS', p_company_branch_id);
  v_id := qcms_private.qcms__indirect_ledger(v_tid, p_company_branch_id, v_item.id, coalesce(p_issue_date, current_date), v_type,
            case when v_type in ('RETURN', 'OPENING') or (v_type = 'ADJUSTMENT' and p_qty > 0) then abs(p_qty) else 0 end,
            case when v_type = 'ISSUE' or (v_type = 'ADJUSTMENT' and p_qty < 0) then abs(p_qty) else 0 end,
            v_item.last_price, 'indirect_items', v_item.id, v_no, nullif(btrim(coalesce(p_department, '')), ''),
            nullif(btrim(coalesce(p_cost_centre, '')), ''), p_issued_to_employee_id, v_item.storage_location, nullif(btrim(coalesce(p_remarks, '')), ''));
  return (select to_jsonb(s) from public.indirect_stock_ledger s where s.id = v_id);
end $$;
revoke all on function public.qcms_issue_indirect_stock(uuid, numeric, uuid, text, text, uuid, date, text, text) from public, anon;
grant execute on function public.qcms_issue_indirect_stock(uuid, numeric, uuid, text, text, uuid, date, text, text) to authenticated;

-- ---------------------------------------------------------------------------------------------------------------
-- 8. In-app notifications (bell + STAWN QCMS mobile app), same pattern as qcms__trg_po_notifications
create or replace function qcms_private.qcms__trg_indirect_po_notifications()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_po text := coalesce(new.po_number, 'draft');
  v_sup text;
  v_key text;
  v_target jsonb;
  v_emp uuid;
begin
  begin
    select coalesce(pt.party_name, pt.party_code) into v_sup from public.parties pt where pt.id = new.supplier_id;
    if new.approval_status = 'PENDING_APPROVAL'
       and (tg_op = 'INSERT' or old.approval_status is distinct from new.approval_status or old.approval_level is distinct from new.approval_level) then
      v_target := public.qcms_indirect_po_approval_target(new.id);
      v_emp := nullif(v_target ->> 'employee_id', '')::uuid;
      v_key := 'IPO_APPROVAL:' || new.id || ':' || coalesce(v_target ->> 'level_no', '1') || ':' || current_date;
      if v_emp is not null then
        perform qcms_private.qcms__add_notification(new.tenant_id, null, v_emp, 'Approval required · Indirect PO ' || v_po,
          'Indirect Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' (INR ' || to_char(coalesce(new.grand_total, 0), 'FM99,99,99,99,990.00') || ') is waiting for your ' ||
          coalesce(v_target ->> 'level_name', 'approval') || coalesce(' (submitted by ' || qcms_private.qcms__emp_name(new.submitted_by_employee_id) || ')', '') || '.',
          'APPROVAL', 'INDIRECT_PURCHASE', 'indirect_purchase_orders', new.id, 'indirect-po-approval', v_key, 'HIGH', new.updated_by);
      end if;
    end if;
    if tg_op = 'UPDATE' and new.approval_status in ('APPROVED', 'REJECTED', 'CANCELLED') and old.approval_status is distinct from new.approval_status then
      v_key := 'IPO_DECISION:' || new.id || ':' || new.approval_status;
      perform qcms_private.qcms__add_notification(new.tenant_id, null, new.submitted_by_employee_id,
        'Indirect PO ' || v_po || ' ' || lower(new.approval_status),
        'Indirect Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' was ' || lower(new.approval_status) ||
        coalesce(' by ' || qcms_private.qcms__emp_name(coalesce(new.approver_employee_id, new.rejected_by_employee_id, new.cancelled_by_employee_id)), '') ||
        coalesce('. Remarks: ' || nullif(btrim(coalesce(new.approval_remarks, new.cancellation_reason, '')), ''), '') || '.',
        case when new.approval_status = 'APPROVED' then 'UPDATE' else 'ALERT' end,
        'INDIRECT_PURCHASE', 'indirect_purchase_orders', new.id, 'indirect-po-list', v_key, 'NORMAL', new.updated_by);
      if new.created_by is not null then
        perform qcms_private.qcms__add_notification(new.tenant_id, new.created_by, null,
          'Indirect PO ' || v_po || ' ' || lower(new.approval_status),
          'Indirect Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' was ' || lower(new.approval_status) || '.',
          case when new.approval_status = 'APPROVED' then 'UPDATE' else 'ALERT' end,
          'INDIRECT_PURCHASE', 'indirect_purchase_orders', new.id, 'indirect-po-list', v_key, 'NORMAL', new.updated_by);
      end if;
    end if;
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_indirect_po_notifications() from public, anon, authenticated;

do $$
begin
  if not exists (select 1 from pg_trigger where tgrelid = 'public.indirect_purchase_orders'::regclass and tgname = 'qcms_r37_indirect_po_notifications') then
    create trigger qcms_r37_indirect_po_notifications after insert or update of approval_status, approval_level on public.indirect_purchase_orders
      for each row execute function qcms_private.qcms__trg_indirect_po_notifications();
  end if;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 9. Global Search: every existing entry kept + Indirect Purchase tables
create or replace function public.qcms_search_table_map()
returns jsonb
language sql
immutable
set search_path = public
as $$
  select '{
    "parts": ["PART_MASTER", "Part Master", "part-records"],
    "part_raw_material_details": ["PART_MASTER", "Part Raw Material", "part-records"],
    "part_raw_material_technical_data": ["PART_MASTER", "Part RM Technical Data", "part-records"],
    "part_supplier_links": ["PART_MASTER", "Part Supplier", "part-records"],
    "part_supplier_price_history": ["PART_MASTER", "Part Supplier Price", "part-records"],
    "part_process_specifications": ["PART_MASTER", "Part Process Specification", "part-records"],
    "part_process_parameter_specifications": ["PART_MASTER", "Part Process Parameter", "part-records"],
    "part_metallurgical_requirements": ["PART_MASTER", "Part Metallurgical Requirement", "part-records"],
    "part_heat_treatment_details": ["PART_MASTER", "Part Heat Treatment", "part-records"],
    "part_rmtc_requirements": ["PART_MASTER", "Part RMTC Requirement", "part-records"],
    "parties": ["REFERENCE_MASTERS", "Customer / Supplier / Vendor", "reference-records"],
    "company_branches": ["REFERENCE_MASTERS", "Company Branch", "company-branch-records"],
    "material_grades": ["MATERIAL_GRADE", "Material Grade", "grade-records"],
    "processes": ["REFERENCE_MASTERS", "Process Master", "process-records"],
    "inspection_stages": ["REFERENCE_MASTERS", "Inspection Stage", "reference-records"],
    "employees": ["EMPLOYEE_MASTER", "Employee", "employee-records"],
    "inspection_plans": ["INSPECTION_LAYOUTS", "Inspection Layout", "inspection-layout-records"],
    "inspection_plan_characteristics": ["INSPECTION_LAYOUTS", "Layout Characteristic", "inspection-layout-records"],
    "rmtc_approvals": ["RMTC_ENTRY", "RMTC", "rmtc-records"],
    "rmtc_part_approvals": ["RMTC_ENTRY", "RMTC Part Approval", "rmtc-records"],
    "inward_lots": ["MATERIAL_INWARD", "Material Inward", "inward-records"],
    "production_batches": ["OSP_TRANSACTIONS", "Production / FSI Batch", "osp-records"],
    "osp_jobs": ["OSP_TRANSACTIONS", "OSP Job / Material Out", "osp-records"],
    "osp_receipts": ["OSP_TRANSACTIONS", "OSP Inward Receipt", "osp-records"],
    "osp_material_outs": ["OSP_TRANSACTIONS", "OSP Material Out", "osp-records"],
    "inspection_reports": ["DIMENSIONAL_REPORT", "Dimensional Report", "dimensional-records"],
    "inspection_results": ["DIMENSIONAL_REPORT", "Dimensional Result", "dimensional-records"],
    "lab_tests": ["METLAB_REPORT", "MetLAB / Bend Test Report", "metlab-records"],
    "quality_complaints": ["COMPLAINT_MANAGEMENT", "Quality Complaint", "complaint-records"],
    "quality_complaint_actions": ["COMPLAINT_MANAGEMENT", "Complaint Action", "complaint-records"],
    "quality_complaint_followups": ["COMPLAINT_MANAGEMENT", "Complaint Follow-up", "complaint-records"],
    "supply_customer_orders": ["SUPPLY_CHAIN", "Customer Order / Schedule", "supply-customer-orders"],
    "supply_purchase_orders": ["SUPPLY_CHAIN", "Purchase Order", "supply-po-order-list"],
    "supply_purchase_order_items": ["SUPPLY_CHAIN", "Purchase Order Item", "supply-po-order-list"],
    "supply_rm_purchase_orders": ["SUPPLY_CHAIN", "RM Procurement Order", "supply-rm-procurement"],
    "supply_rm_receipts": ["SUPPLY_CHAIN", "RM Receipt", "supply-rm-receipt"],
    "supply_rm_dispatches": ["SUPPLY_CHAIN", "RM to Forging", "supply-rm-dispatch"],
    "supply_forging_orders": ["SUPPLY_CHAIN", "Forging Order", "supply-forging"],
    "supply_forging_receipts": ["SUPPLY_CHAIN", "Forging Receipt", "supply-forging"],
    "supply_downstream_events": ["SUPPLY_CHAIN", "Machining / FG / Dispatch", "supply-downstream"],
    "supply_opening_stock": ["SUPPLY_CHAIN", "Opening Stock", "supply-opening-stock"],
    "supply_po_confirmations": ["SUPPLY_CHAIN", "PO Confirmation", "supply-po-order-list"],
    "npd_orders": ["NPD_APQP", "NPD Order", "npd-status"],
    "npd_order_steps": ["NPD_APQP", "NPD Step", "npd-status"],
    "npd_process_flows": ["NPD_APQP", "Process Flow", "npd-process-flow"],
    "npd_process_flow_steps": ["NPD_APQP", "Process Flow Step", "npd-process-flow"],
    "ppap_projects": ["NPD_APQP", "APQP / PPAP Project", "apqp"],
    "ppap_documents": ["NPD_APQP", "PPAP Document", "apqp"],
    "quality_assets": ["CALIBRATION_VALIDATION", "Gauge / Fixture / Instrument", "calibration-validation"],
    "quality_asset_calibration_records": ["CALIBRATION_VALIDATION", "Calibration / Validation Record", "calibration-validation"],
    "standard_room_inspection_records": ["CALIBRATION_VALIDATION", "Standard Room Inspection", "standard-room-inspection"],
    "standard_room_inspections": ["CALIBRATION_VALIDATION", "Standard Room Inspection", "standard-room-inspection"],
    "standard_room_instruments": ["CALIBRATION_VALIDATION", "Standard Room Instrument", "standard-room-inspection"],
    "customer_standards": ["REFERENCE_MASTERS", "Customer Standard", "standards-records"],
    "standards_register": ["REFERENCE_MASTERS", "Standards Register", "standards-records"],
    "qc_calculation_records": ["QC_CALCULATION_TOOLS", "QC Calculation", "qc-calculation-records"],
    "material_grade_elements": ["MATERIAL_GRADE", "Material Grade Chemistry", "grade-records"],
    "part_material_grade_links": ["PART_MASTER", "Part Material Grade", "part-records"],
    "part_jominy_requirements": ["PART_MASTER", "Part Jominy Requirement", "part-records"],
    "part_standard_links": ["PART_MASTER", "Part Standard Link", "part-records"],
    "test_plans": ["INSPECTION_LAYOUTS", "Test Plan", "inspection-layout-records"],
    "gauge_fixture_assets": ["CALIBRATION_VALIDATION", "Gauge / Fixture", "calibration-validation"],
    "gauge_fixture_control_records": ["CALIBRATION_VALIDATION", "Gauge / Fixture Control Record", "calibration-validation"],
    "quality_asset_part_process_links": ["CALIBRATION_VALIDATION", "Gauge Part / Process Link", "calibration-validation"],
    "calibration_events": ["CALIBRATION_VALIDATION", "Calibration Event", "calibration-validation"],
    "rmtc_chemistry_results": ["RMTC_ENTRY", "RMTC Chemistry Result", "rmtc-records"],
    "rmtc_requirement_results": ["RMTC_ENTRY", "RMTC Requirement Result", "rmtc-records"],
    "rmtc_jominy_results": ["RMTC_ENTRY", "RMTC Jominy Result", "rmtc-records"],
    "rmtc_decision_revisions": ["RMTC_ENTRY", "RMTC Decision Revision", "rmtc-records"],
    "supply_purchase_order_sources": ["SUPPLY_CHAIN", "PO Customer Order Source", "supply-po-order-list"],
    "batch_movements": ["OSP_TRANSACTIONS", "Batch Movement", "osp-records"],
    "dispatches": ["SUPPLY_CHAIN", "Dispatch", "supply-downstream"],
    "dispatch_batches": ["SUPPLY_CHAIN", "Dispatch Batch", "supply-downstream"],
    "customer_report_packages": ["DIMENSIONAL_REPORT", "Customer Report Package", "records-center"],
    "customer_report_package_items": ["DIMENSIONAL_REPORT", "Customer Report Package Item", "records-center"],
    "control_plan_headers": ["NPD_APQP", "Control Plan", "apqp"],
    "control_plan_items": ["NPD_APQP", "Control Plan Item", "apqp"],
    "pfd_headers": ["NPD_APQP", "Process Flow Diagram", "apqp"],
    "pfd_steps": ["NPD_APQP", "PFD Step", "apqp"],
    "pfmea_headers": ["NPD_APQP", "PFMEA", "apqp"],
    "pfmea_items": ["NPD_APQP", "PFMEA Item", "apqp"],
    "msa_plans": ["NPD_APQP", "MSA Plan", "apqp"],
    "msa_studies": ["NPD_APQP", "MSA Study", "apqp"],
    "spc_plans": ["NPD_APQP", "SPC Plan", "apqp"],
    "spc_studies": ["NPD_APQP", "SPC Study", "apqp"],
    "capacity_studies": ["NPD_APQP", "Capacity Study", "apqp"],
    "balloon_characteristics": ["NPD_APQP", "Balloon Characteristic", "apqp"],
    "npd_order_step_points": ["NPD_APQP", "NPD Step Point", "npd-status"],
    "npd_process_flow_points": ["NPD_APQP", "Process Flow Point", "npd-process-flow"],
    "audit_plans": [null, "Audit Plan", "records-center"],
    "audit_findings": [null, "Audit Finding", "records-center"],
    "document_approvals": [null, "Document Approval", "records-center"],
    "calculation_rules": ["QC_CALCULATION_TOOLS", "Calculation Rule", "qc-tools"],
    "document_attachments": [null, "Attachment / Photo", "records-center"],
    "qcms_delete_requests": [null, "Deletion Request", "records-center"],
    "indirect_items": ["INDIRECT_PURCHASE", "Indirect Item", "indirect-items"],
    "indirect_item_categories": ["INDIRECT_PURCHASE", "Indirect Item Category", "indirect-items"],
    "indirect_purchase_requisitions": ["INDIRECT_PURCHASE", "Indirect Purchase Requisition", "indirect-requisition"],
    "indirect_purchase_requisition_items": ["INDIRECT_PURCHASE", "Indirect Requisition Item", "indirect-requisition"],
    "indirect_purchase_orders": ["INDIRECT_PURCHASE", "Indirect Purchase Order", "indirect-po-list"],
    "indirect_purchase_order_items": ["INDIRECT_PURCHASE", "Indirect PO Item", "indirect-po-list"],
    "indirect_grns": ["INDIRECT_PURCHASE", "Indirect Inward (GRN)", "indirect-inward"],
    "indirect_grn_items": ["INDIRECT_PURCHASE", "Indirect GRN Item", "indirect-inward"],
    "indirect_stock_ledger": ["INDIRECT_PURCHASE", "Indirect Stock Ledger", "indirect-stock"]
  }'::jsonb
$$;
grant execute on function public.qcms_search_table_map() to authenticated;

notify pgrst, 'reload schema';

-- ---------------------------------------------------------------------------------------------------------------
-- 10. R37 completion: gate entry on the Indirect GRN and an over-receipt tolerance per Indirect PO.
--     Received quantity per PO line may reach ordered × (1 + tolerance %) minus the quantity already accepted;
--     the PO closes when every line is accepted in full.
alter table public.indirect_grns add column if not exists gate_entry_no text;
alter table public.indirect_grns add column if not exists gate_entry_date date;
alter table public.indirect_purchase_orders add column if not exists over_receipt_tolerance_percent numeric not null default 0
  check (over_receipt_tolerance_percent >= 0 and over_receipt_tolerance_percent <= 50);

create or replace function public.qcms_post_indirect_grn(p_grn_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tid uuid := public.current_tenant_id();
  g public.indirect_grns%rowtype;
  po public.indirect_purchase_orders%rowtype;
  l record;
  poi public.indirect_purchase_order_items%rowtype;
  v_status text;
  v_lines integer := 0;
  v_tol numeric;
  v_allowed numeric;
begin
  if auth.uid() is null or v_tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_indirect_purchase_can_write() then raise exception 'Indirect Purchase create / edit permission is required'; end if;
  select * into g from public.indirect_grns where id = p_grn_id and tenant_id = v_tid for update;
  if g.id is null then raise exception 'GRN not found'; end if;
  if g.status <> 'DRAFT' then raise exception 'GRN % is already %', g.grn_number, g.status; end if;
  for l in select * from public.indirect_grn_items where grn_id = g.id loop
    v_lines := v_lines + 1;
    if abs(coalesce(l.accepted_qty, 0) + coalesce(l.rejected_qty, 0) - coalesce(l.received_qty, 0)) > 0.0005 then
      raise exception 'Line %: accepted + rejected must equal received quantity', l.line_no;
    end if;
    if coalesce(l.rejected_qty, 0) > 0 and length(btrim(coalesce(l.rejection_reason, ''))) = 0 then
      raise exception 'Line %: enter the rejection reason', l.line_no;
    end if;
  end loop;
  if v_lines = 0 then raise exception 'The GRN has no lines'; end if;

  perform set_config('qcms.indirect_rpc', 'on', true);
  if g.grn_type = 'WITHOUT_PO' then
    update public.indirect_grns set status = 'PENDING_APPROVAL', approval_status = 'PENDING_APPROVAL', updated_at = now(), updated_by = auth.uid()
     where id = g.id returning * into g;
    perform set_config('qcms.indirect_rpc', 'off', true);
    return to_jsonb(g);
  end if;

  select * into po from public.indirect_purchase_orders where id = g.purchase_order_id and tenant_id = v_tid for update;
  if po.id is null then raise exception 'The GRN is not linked to an Indirect Purchase Order'; end if;
  if po.approval_status <> 'APPROVED' or po.status not in ('APPROVED', 'PARTIALLY_RECEIVED') then
    raise exception 'Indirect PO % is % – only an approved, open PO can be received', po.po_number, po.status;
  end if;
  v_tol := least(greatest(coalesce(po.over_receipt_tolerance_percent, 0), 0), 50);
  for l in select * from public.indirect_grn_items where grn_id = g.id order by line_no loop
    if l.po_item_id is null then raise exception 'Line %: PO line is missing', l.line_no; end if;
    select * into poi from public.indirect_purchase_order_items where id = l.po_item_id and purchase_order_id = po.id for update;
    if poi.id is null then raise exception 'Line %: PO line does not belong to %', l.line_no, po.po_number; end if;
    v_allowed := poi.quantity * (1 + v_tol / 100.0) - poi.accepted_qty;
    if coalesce(l.received_qty, 0) > v_allowed + 0.0005 then
      raise exception 'Line % (%): received % exceeds the receivable balance % % (ordered %, tolerance % %%)', l.line_no,
        coalesce(poi.item_code, poi.item_name), round(l.received_qty, 3), round(greatest(v_allowed, 0), 3), poi.uom,
        round(poi.quantity, 3), round(v_tol, 2);
    end if;
    update public.indirect_purchase_order_items
       set received_qty = received_qty + coalesce(l.received_qty, 0), accepted_qty = accepted_qty + coalesce(l.accepted_qty, 0),
           rejected_qty = rejected_qty + coalesce(l.rejected_qty, 0), updated_at = now(), updated_by = auth.uid()
     where id = poi.id;
  end loop;
  select case when bool_and(accepted_qty + 0.0005 >= quantity) then 'CLOSED'
              when bool_or(received_qty > 0) then 'PARTIALLY_RECEIVED' else po.status end
    into v_status from public.indirect_purchase_order_items where purchase_order_id = po.id;
  update public.indirect_purchase_orders set status = v_status, updated_at = now(), updated_by = auth.uid() where id = po.id;
  perform qcms_private.qcms__indirect_grn_to_stock(g.id);
  update public.indirect_grns set status = 'POSTED', posted_at = now(), updated_at = now(), updated_by = auth.uid()
   where id = g.id returning * into g;
  perform set_config('qcms.indirect_rpc', 'off', true);
  return to_jsonb(g) || jsonb_build_object('po_status', v_status);
end $$;
revoke all on function public.qcms_post_indirect_grn(uuid) from public, anon;
grant execute on function public.qcms_post_indirect_grn(uuid) to authenticated;

notify pgrst, 'reload schema';
