-- QCMS v4.14.49 R37 · OSP Material Out returnable delivery challan, vendor return entries,
-- OSP layout process fallback in the Dimensional / MetLAB save triggers.
-- Safe to re-run: create table if not exists / add column if not exists / create or replace / guarded policies.
-- No business data is changed by this file.

-- ---------------------------------------------------------------------------------------------
-- 1. Challan header (one per Material Out document, or per legacy single OSP job)
-- ---------------------------------------------------------------------------------------------
create table if not exists public.osp_challans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  material_out_id uuid references public.osp_material_outs(id) on delete cascade,
  osp_job_id uuid references public.osp_jobs(id) on delete cascade,
  challan_number text not null,
  challan_date date not null default current_date,
  branch_id uuid references public.company_branches(id),
  vendor_id uuid references public.parties(id),
  ship_to_party_id uuid references public.parties(id),
  ship_to_text text,
  user_name text,
  ship_via text,
  incoterm text,
  delivery_date date,
  payment_term text,
  reference_details text,
  old_po_details text,
  process_text text,
  vehicle_number text,
  transporter_name text,
  eway_bill_number text,
  shipping_amount numeric(14,2) not null default 0,
  other_amount numeric(14,2) not null default 0,
  remarks text,
  status text not null default 'ISSUED',
  emailed_at timestamptz,
  emailed_to text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  constraint osp_challans_one_source check ((material_out_id is null) <> (osp_job_id is null)),
  constraint osp_challans_status_check check (status in ('DRAFT', 'ISSUED', 'CLOSED', 'CANCELLED')),
  constraint osp_challans_amounts_check check (shipping_amount >= 0 and other_amount >= 0)
);
create unique index if not exists osp_challans_material_out_uq on public.osp_challans (tenant_id, material_out_id) where material_out_id is not null;
create unique index if not exists osp_challans_job_uq on public.osp_challans (tenant_id, osp_job_id) where osp_job_id is not null;
create index if not exists osp_challans_number_idx on public.osp_challans (tenant_id, upper(challan_number));
create index if not exists osp_challans_vendor_idx on public.osp_challans (tenant_id, vendor_id, challan_date desc);

-- ---------------------------------------------------------------------------------------------
-- 2. Challan commercial lines (one per OSP heat job): FSI item, UOM, price, GST, batch code
-- ---------------------------------------------------------------------------------------------
create table if not exists public.osp_challan_lines (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  challan_id uuid not null references public.osp_challans(id) on delete cascade,
  osp_job_id uuid not null references public.osp_jobs(id) on delete cascade,
  line_no integer not null default 1,
  item_code text,
  item_description text,
  hsn_code text,
  uom text not null default 'NOS',
  unit_price numeric(14,4) not null default 0,
  gst_percent numeric(5,2) not null default 18,
  batch_code text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  constraint osp_challan_lines_values_check check (unit_price >= 0 and gst_percent >= 0 and gst_percent <= 100)
);
create unique index if not exists osp_challan_lines_job_uq on public.osp_challan_lines (challan_id, osp_job_id);
create index if not exists osp_challan_lines_job_idx on public.osp_challan_lines (tenant_id, osp_job_id);

-- ---------------------------------------------------------------------------------------------
-- 3. Vendor return challan / invoice entries.
--    osp_receipt_id set   -> supplements an OSP Inward receipt (vehicle no, rejected qty); the returned
--                            quantity is the receipt quantity (never counted twice).
--    osp_receipt_id null  -> material returned without OSP Inward (e.g. unprocessed / rejected return).
-- ---------------------------------------------------------------------------------------------
create table if not exists public.osp_challan_returns (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  challan_id uuid not null references public.osp_challans(id) on delete cascade,
  osp_job_id uuid references public.osp_jobs(id) on delete cascade,
  osp_receipt_id uuid references public.osp_receipts(id) on delete cascade,
  vendor_challan_number text,
  vendor_challan_date date,
  vendor_invoice_number text,
  vendor_invoice_date date,
  quantity_returned numeric(14,3) not null default 0,
  quantity_rejected numeric(14,3) not null default 0,
  vehicle_number text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  constraint osp_challan_returns_qty_check check (quantity_returned >= 0 and quantity_rejected >= 0)
);
create unique index if not exists osp_challan_returns_receipt_uq on public.osp_challan_returns (osp_receipt_id) where osp_receipt_id is not null;
create index if not exists osp_challan_returns_challan_idx on public.osp_challan_returns (tenant_id, challan_id);

-- ---------------------------------------------------------------------------------------------
-- 4. RLS · tenant read, OSP Transactions create / edit / archive permissions for writes
-- ---------------------------------------------------------------------------------------------
alter table public.osp_challans enable row level security;
alter table public.osp_challan_lines enable row level security;
alter table public.osp_challan_returns enable row level security;

do $$
declare t text;
begin
  foreach t in array array['osp_challans', 'osp_challan_lines', 'osp_challan_returns'] loop
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_select') then
      execute format('create policy %I on public.%I for select to authenticated using (tenant_id = public.current_tenant_id())', t || '_select', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_insert') then
      execute format('create policy %I on public.%I for insert to authenticated with check (tenant_id = public.current_tenant_id() and (public.qcms_effective_module_permission(''OSP_TRANSACTIONS'', ''create'') or public.qcms_effective_module_permission(''OSP_TRANSACTIONS'', ''edit'')))', t || '_insert', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_update') then
      execute format('create policy %I on public.%I for update to authenticated using (tenant_id = public.current_tenant_id() and public.qcms_effective_module_permission(''OSP_TRANSACTIONS'', ''edit'')) with check (tenant_id = public.current_tenant_id() and public.qcms_effective_module_permission(''OSP_TRANSACTIONS'', ''edit''))', t || '_update', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = t || '_delete') then
      execute format('create policy %I on public.%I for delete to authenticated using (tenant_id = public.current_tenant_id() and public.qcms_effective_module_permission(''OSP_TRANSACTIONS'', ''archive''))', t || '_delete', t);
    end if;
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
    execute format('revoke all on public.%I from anon', t);
  end loop;
end $$;

-- updated_at / audit triggers (same functions as the other OSP tables)
do $$
declare t text;
begin
  foreach t in array array['osp_challans', 'osp_challan_lines', 'osp_challan_returns'] loop
    if not exists (select 1 from pg_trigger where tgname = 'trg_touch_updated_at' and tgrelid = ('public.' || t)::regclass) then
      execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', t);
    end if;
    if not exists (select 1 from pg_trigger where tgname = 'trg_audit_row_change' and tgrelid = ('public.' || t)::regclass) then
      execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()', t);
    end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 5. Challan number series per branch: JWC + plant code + 5 digits (JWCD901026 -> JWCD901027).
--    Reads existing challan numbers and Material Out challans; the number stays editable in the app.
-- ---------------------------------------------------------------------------------------------
create or replace function public.qcms_next_osp_challan_number(p_branch_id uuid default null)
returns text language plpgsql stable security invoker set search_path = public as $$
declare
  v_code text;
  v_prefix text;
  v_max bigint;
begin
  if p_branch_id is not null then
    select coalesce(nullif(btrim(plant_code), ''), nullif(btrim(branch_code), '')) into v_code
      from public.company_branches where id = p_branch_id and tenant_id = public.current_tenant_id();
  end if;
  if v_code is null then
    select coalesce(nullif(btrim(plant_code), ''), nullif(btrim(branch_code), '')) into v_code
      from public.company_branches where tenant_id = public.current_tenant_id() and status = 'ACTIVE'
     order by is_default desc, created_at limit 1;
  end if;
  v_prefix := 'JWC' || upper(regexp_replace(coalesce(v_code, 'D9'), '[^A-Za-z0-9]', '', 'g'));
  select max(substring(n from length(v_prefix) + 1)::bigint) into v_max
    from (
      select upper(btrim(challan_number)) as n from public.osp_challans where tenant_id = public.current_tenant_id()
      union all
      select upper(btrim(dispatch_challan)) from public.osp_jobs where tenant_id = public.current_tenant_id()
    ) s
   where n ~ ('^' || v_prefix || '[0-9]{1,12}$');
  return v_prefix || lpad((coalesce(v_max, 0) + 1)::text, 5, '0');
end $$;
revoke all on function public.qcms_next_osp_challan_number(uuid) from public, anon;
grant execute on function public.qcms_next_osp_challan_number(uuid) to authenticated;

-- ---------------------------------------------------------------------------------------------
-- 6. OSP layout acceptance (R37): exact Part + Process, or the R35 fallback for a layout registered
--    under the wrong Process in Layout Master:
--      a) approved OSP layout of the same Part whose name contains the batch's process name, or
--      b) the only approved OSP layout of that type for the Part, at an OSP inspection stage, whose
--         Process is not one of the Part's own active OSP processes (i.e. clearly mis-registered).
-- ---------------------------------------------------------------------------------------------
create or replace function public.qcms_osp_layout_acceptable(p_plan_id uuid, p_osp_job_id uuid, p_layout_type text)
returns boolean language plpgsql stable security definer set search_path = public as $$
declare
  j record;
  p public.inspection_plans%rowtype;
  v_name text;
begin
  select o.part_id, o.process_id, o.tenant_id, pr.process_name into j
    from public.osp_jobs o left join public.processes pr on pr.id = o.process_id
   where o.id = p_osp_job_id;
  select * into p from public.inspection_plans where id = p_plan_id;
  if j.part_id is null or p.id is null then return false; end if;
  if p.tenant_id <> j.tenant_id or p.part_id <> j.part_id or p.inward_type <> 'OSP_PROCESS'
     or p.layout_type <> p_layout_type or p.status <> 'APPROVED' then
    return false;
  end if;
  if p.process_id = j.process_id then return true; end if;
  v_name := lower(regexp_replace(btrim(coalesce(j.process_name, '')), '\s+', ' ', 'g'));
  if length(v_name) >= 3 and position(v_name in lower(regexp_replace(coalesce(p.layout_name, ''), '\s+', ' ', 'g'))) > 0 then
    return true;
  end if;
  return not exists (
           select 1 from public.inspection_plans x
            where x.tenant_id = j.tenant_id and x.part_id = j.part_id and x.inward_type = 'OSP_PROCESS'
              and x.layout_type = p_layout_type and x.status = 'APPROVED' and x.id <> p.id)
     and exists (
           select 1 from public.inspection_stages s
            where s.id = p.inspection_stage_id
              and upper(coalesce(s.stage_code, '') || ' ' || coalesce(s.stage_name, '')) like '%OSP%')
     and not exists (
           select 1 from public.part_process_specifications ps
            where ps.tenant_id = j.tenant_id and ps.part_id = j.part_id and ps.inward_type = 'OSP_PROCESS'
              and ps.status = 'ACTIVE' and ps.process_id = p.process_id);
end $$;
-- Only the SECURITY DEFINER save triggers call it (as owner); not exposed through the REST API.
revoke all on function public.qcms_osp_layout_acceptable(uuid, uuid, text) from public, anon, authenticated;

-- Live definitions copied; only the layout check changed (exact Part+Process -> qcms_osp_layout_acceptable).
CREATE OR REPLACE FUNCTION public.enforce_osp_dimensional_source()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'auth'
AS $function$ declare job_row public.osp_jobs%rowtype;plan_row public.inspection_plans%rowtype; begin if new.osp_job_id is null then new.inspection_scope:='MATERIAL_INWARD'; return new; end if; select * into job_row from public.osp_jobs where id=new.osp_job_id; if job_row.id is null or job_row.tenant_id<>new.tenant_id then raise exception 'Invalid OSP job for Dimensional inspection'; end if; if new.inspection_scope not in ('OSP_SAMPLE','OSP_RECEIPT') then raise exception 'Select OSP Sample or OSP Receipt inspection scope'; end if; if new.inspection_scope='OSP_SAMPLE' and job_row.sample_received_date is null then raise exception 'Record the one-part OSP sample receipt before inspection'; end if; if new.inspection_scope='OSP_RECEIPT' and job_row.quantity_received<=0 then raise exception 'Full OSP inward is required before receipt inspection'; end if; select * into plan_row from public.inspection_plans where id=new.inspection_plan_id; if plan_row.id is null or not public.qcms_osp_layout_acceptable(plan_row.id, job_row.id, 'DIMENSIONAL') then raise exception 'Use an Approved OSP Dimensional layout matching the Part and Process (a layout of this Part whose name contains the OSP process is also accepted)'; end if; new.inward_lot_id:=null;new.part_id:=job_row.part_id;new.process_id:=job_row.process_id;new.batch_id:=job_row.osp_batch_id;new.heat_number:=(select heat_number from public.production_batches where id=job_row.source_batch_id);new.heat_code:=(select heat_code from public.production_batches where id=job_row.source_batch_id);new.supplier_id:=job_row.vendor_id;new.process_specification_snapshot:=job_row.process_specification;new.vendor_batch_number_snapshot:=job_row.vendor_batch_number;new.production_quantity_pcs:=case when new.inspection_scope='OSP_SAMPLE' then job_row.sample_quantity else job_row.quantity_received end;new.lot_quantity:=new.production_quantity_pcs;return new; end; $function$;

CREATE OR REPLACE FUNCTION public.enforce_osp_metlab_source()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'auth'
AS $function$ declare job_row public.osp_jobs%rowtype;plan_row public.inspection_plans%rowtype; begin if new.osp_job_id is null then new.inspection_scope:='MATERIAL_INWARD'; return new; end if; select * into job_row from public.osp_jobs where id=new.osp_job_id; if job_row.id is null or job_row.tenant_id<>new.tenant_id then raise exception 'Invalid OSP job for MetLAB inspection'; end if; if new.inspection_scope not in ('OSP_SAMPLE','OSP_RECEIPT') then raise exception 'Select OSP Sample or OSP Receipt inspection scope'; end if; if new.inspection_scope='OSP_SAMPLE' and job_row.sample_received_date is null then raise exception 'Record the one-part OSP sample receipt before inspection'; end if; if new.inspection_scope='OSP_RECEIPT' and job_row.quantity_received<=0 then raise exception 'Full OSP inward is required before receipt inspection'; end if; select * into plan_row from public.inspection_plans where id=new.layout_plan_id; if plan_row.id is null or not public.qcms_osp_layout_acceptable(plan_row.id, job_row.id, 'METLAB') then raise exception 'Use an Approved OSP MetLAB layout matching the Part and Process (a layout of this Part whose name contains the OSP process is also accepted)'; end if; new.inward_lot_id:=null;new.part_id:=job_row.part_id;new.process_id:=job_row.process_id;new.batch_id:=job_row.osp_batch_id;new.heat_number:=(select heat_number from public.production_batches where id=job_row.source_batch_id);new.heat_code:=(select heat_code from public.production_batches where id=job_row.source_batch_id);new.supplier_id:=job_row.vendor_id;new.process_specification_snapshot:=job_row.process_specification;new.vendor_batch_number_snapshot:=job_row.vendor_batch_number;new.production_quantity_pcs:=case when new.inspection_scope='OSP_SAMPLE' then job_row.sample_quantity else job_row.quantity_received end;return new; end; $function$;
