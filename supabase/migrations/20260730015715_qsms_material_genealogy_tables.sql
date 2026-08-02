-- QSMS material genealogy and OSP
begin;

-- -----------------------------------------------------------------------------
-- RMTC, inward, batch genealogy and OSP
-- -----------------------------------------------------------------------------
create table if not exists public.rmtc_approvals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  rmtc_number text not null,
  certificate_date date not null,
  certificate_reference text,
  part_id uuid not null references public.parts(id),
  supplier_id uuid not null references public.parties(id),
  steel_mill_id uuid not null references public.parties(id),
  material_grade_id uuid not null references public.material_grades(id),
  heat_number text not null,
  heat_code text not null,
  certificate_quantity numeric not null default 0 check (certificate_quantity >= 0),
  chemistry_results jsonb not null default '{}'::jsonb,
  chemistry_compliance text not null default 'NOT_EVALUATED' check (chemistry_compliance in ('PASS','FAIL','NOT_EVALUATED')),
  chemistry_failures jsonb not null default '[]'::jsonb,
  mechanical_results jsonb not null default '{}'::jsonb,
  status text not null default 'DRAFT' check (status in ('DRAFT','APPROVAL_PENDING','APPROVED','REJECTED','SUPERSEDED')),
  approved_at timestamptz,
  approved_by uuid references public.profiles(id),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  check (status <> 'APPROVED' or chemistry_compliance = 'PASS'),
  unique (tenant_id, rmtc_number)
);

create table if not exists public.inward_lots (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  inward_number text not null,
  inward_date date not null,
  grn_number text not null,
  invoice_number text,
  part_id uuid not null references public.parts(id),
  supplier_id uuid not null references public.parties(id),
  rmtc_approval_id uuid not null references public.rmtc_approvals(id),
  heat_number text not null,
  heat_code text not null,
  quantity_received numeric not null check (quantity_received > 0),
  quantity_accepted numeric not null default 0 check (quantity_accepted >= 0),
  quantity_rejected numeric not null default 0 check (quantity_rejected >= 0),
  metallurgical_status text not null default 'PENDING' check (metallurgical_status in ('PENDING','PASS','FAIL','NOT_REQUIRED','HOLD')),
  dimensional_status text not null default 'PENDING' check (dimensional_status in ('PENDING','PASS','FAIL','NOT_REQUIRED','HOLD')),
  status text not null default 'HOLD_PENDING_INSPECTION' check (status in ('HOLD_PENDING_INSPECTION','RELEASED','REJECTED','CLOSED')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  check (quantity_accepted + quantity_rejected <= quantity_received),
  check (
    status <> 'RELEASED' or
    (metallurgical_status in ('PASS','NOT_REQUIRED') and dimensional_status in ('PASS','NOT_REQUIRED'))
  ),
  unique (tenant_id, inward_number),
  unique (tenant_id, grn_number, part_id, heat_number)
);

create table if not exists public.production_batches (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  batch_code text not null,
  part_id uuid not null references public.parts(id),
  inward_lot_id uuid not null references public.inward_lots(id),
  parent_batch_id uuid references public.production_batches(id),
  heat_number text not null,
  heat_code text not null,
  vendor_batch_number text,
  current_process_id uuid references public.processes(id),
  work_order text,
  quantity_started numeric not null check (quantity_started > 0),
  quantity_available numeric not null default 0 check (quantity_available >= 0 and quantity_available <= quantity_started),
  status text not null default 'IN_PROCESS',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, batch_code)
);

create table if not exists public.batch_movements (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  batch_id uuid not null references public.production_batches(id) on delete cascade,
  movement_type text not null,
  from_process_id uuid references public.processes(id),
  to_process_id uuid references public.processes(id),
  quantity numeric not null check (quantity >= 0),
  movement_date date not null,
  reference text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.osp_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  osp_job_number text not null,
  source_batch_id uuid not null references public.production_batches(id),
  osp_batch_id uuid not null references public.production_batches(id),
  part_id uuid not null references public.parts(id),
  vendor_id uuid not null references public.parties(id),
  process_id uuid not null references public.processes(id),
  dispatch_date date not null,
  dispatch_challan text not null,
  quantity_dispatched numeric not null check (quantity_dispatched > 0),
  expected_return_date date,
  process_specification text,
  required_tests text[] not null default '{}'::text[],
  receipt_date date,
  receipt_challan text,
  vendor_batch_number text,
  quantity_received numeric not null default 0 check (quantity_received >= 0),
  quantity_rejected_at_receipt numeric not null default 0 check (quantity_rejected_at_receipt >= 0),
  receipt_status text not null default 'PENDING' check (receipt_status in ('PENDING','PARTIAL','COMPLETE')),
  inspection_status text not null default 'PENDING' check (inspection_status in ('PENDING','PASS','FAIL','HOLD')),
  status text not null default 'AT_VENDOR' check (status in ('AT_VENDOR','PART_RECEIVED','COMPLETED','REJECTED','CANCELLED')),
  receipt_remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  check (quantity_received <= quantity_dispatched),
  check (quantity_rejected_at_receipt <= quantity_received),
  check (
    quantity_received = 0 or
    (receipt_date is not null and nullif(btrim(coalesce(receipt_challan,'')), '') is not null
     and nullif(btrim(coalesce(vendor_batch_number,'')), '') is not null)
  ),
  unique (tenant_id, osp_job_number)
);

-- RMTC approval guard: inherit the part's controlled material grade and require
-- a currently approved source link before certificate approval.
create or replace function public.enforce_rmtc_master_link()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  part_row public.parts%rowtype;
  source_is_approved boolean;
  already_received numeric;
begin
  select * into part_row from public.parts where id = new.part_id;
  if part_row.id is null or part_row.tenant_id <> new.tenant_id then
    raise exception 'Invalid part for RMTC approval';
  end if;
  if part_row.material_grade_id is null then
    raise exception 'The selected part has no controlled material grade';
  end if;
  new.material_grade_id := part_row.material_grade_id;
  select coalesce(sum(quantity_received), 0)
    into already_received
  from public.inward_lots
  where rmtc_approval_id = new.id;
  if already_received > new.certificate_quantity then
    raise exception 'RMTC certificate quantity cannot be reduced below material already inwarded';
  end if;

  if new.status = 'APPROVED' then
    select exists (
      select 1
      from public.part_supplier_links link
      where link.tenant_id = new.tenant_id
        and link.part_id = new.part_id
        and link.supplier_id = new.supplier_id
        and (link.steel_mill_id is null or link.steel_mill_id = new.steel_mill_id)
        and link.approved is true
        and (link.valid_from is null or link.valid_from <= current_date)
        and (link.valid_to is null or link.valid_to >= current_date)
    ) into source_is_approved;
    if not source_is_approved then
      raise exception 'RMTC approval requires a valid approved part-supplier-steel-mill source link';
    end if;
    if new.chemistry_compliance <> 'PASS' then
      raise exception 'RMTC approval requires PASS chemistry compliance';
    end if;
    if new.certificate_quantity <= 0 then
      raise exception 'RMTC approval requires a positive certificate quantity';
    end if;
    new.approved_at := now();
    new.approved_by := auth.uid();
  end if;
  return new;
end;
$$;

revoke all on function public.enforce_rmtc_master_link() from public, anon, authenticated;

drop trigger if exists trg_rmtc_master_link on public.rmtc_approvals;
create trigger trg_rmtc_master_link
before insert or update of part_id, supplier_id, steel_mill_id, material_grade_id, status, chemistry_compliance, certificate_quantity
on public.rmtc_approvals
for each row execute function public.enforce_rmtc_master_link();

-- Genealogy guard: inward can only be created against an approved, matching RMTC.
create or replace function public.enforce_inward_rmtc_link()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  cert public.rmtc_approvals%rowtype;
  already_received numeric;
  allocated_to_batches numeric;
begin
  select * into cert from public.rmtc_approvals where id = new.rmtc_approval_id;
  if cert.id is null then
    raise exception 'Linked RMTC approval does not exist';
  end if;
  if cert.status <> 'APPROVED' then
    raise exception 'Material inward is allowed only against an approved RMTC';
  end if;
  if cert.tenant_id <> new.tenant_id then
    raise exception 'RMTC and inward tenant mismatch';
  end if;
  new.part_id := cert.part_id;
  new.supplier_id := cert.supplier_id;
  new.heat_number := cert.heat_number;
  new.heat_code := cert.heat_code;
  select coalesce(sum(quantity_received), 0)
    into already_received
  from public.inward_lots
  where rmtc_approval_id = cert.id
    and (new.id is null or id <> new.id);
  if already_received + new.quantity_received > cert.certificate_quantity then
    raise exception 'Material inward quantity exceeds the approved RMTC certificate balance';
  end if;
  select coalesce(sum(quantity_started), 0)
    into allocated_to_batches
  from public.production_batches
  where inward_lot_id = new.id and parent_batch_id is null;
  if allocated_to_batches > new.quantity_accepted then
    raise exception 'Accepted inward quantity cannot be reduced below quantity already allocated to production batches';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_inward_rmtc_link on public.inward_lots;
create trigger trg_inward_rmtc_link
before insert or update of rmtc_approval_id, part_id, supplier_id, heat_number, heat_code, quantity_received, quantity_accepted
on public.inward_lots
for each row execute function public.enforce_inward_rmtc_link();

-- Genealogy guard: every child batch inherits part, inward lot and heat identity.
create or replace function public.enforce_batch_genealogy()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  inward_row public.inward_lots%rowtype;
  parent_row public.production_batches%rowtype;
  allocated_quantity numeric;
  direct_children_quantity numeric;
begin
  select * into inward_row from public.inward_lots where id = new.inward_lot_id;
  if inward_row.id is null or inward_row.tenant_id <> new.tenant_id then
    raise exception 'Invalid inward lot for production batch';
  end if;
  if inward_row.status <> 'RELEASED' then
    raise exception 'Production batch requires a released inward lot';
  end if;
  if new.parent_batch_id is not null then
    select * into parent_row from public.production_batches where id = new.parent_batch_id;
    if parent_row.id is null or parent_row.tenant_id <> new.tenant_id then
      raise exception 'Invalid parent batch';
    end if;
    if parent_row.part_id <> inward_row.part_id or parent_row.inward_lot_id <> inward_row.id then
      raise exception 'Parent batch genealogy does not match the inward lot';
    end if;
    select coalesce(sum(quantity_started), 0)
      into allocated_quantity
    from public.production_batches
    where parent_batch_id = parent_row.id
      and (new.id is null or id <> new.id);
    if allocated_quantity + new.quantity_started > parent_row.quantity_started then
      raise exception 'Child batch quantity exceeds the parent batch quantity balance';
    end if;
  else
    select coalesce(sum(quantity_started), 0)
      into allocated_quantity
    from public.production_batches
    where inward_lot_id = inward_row.id
      and parent_batch_id is null
      and (new.id is null or id <> new.id);
    if allocated_quantity + new.quantity_started > inward_row.quantity_accepted then
      raise exception 'Production batch quantity exceeds the accepted inward quantity balance';
    end if;
  end if;

  select coalesce(sum(quantity_started), 0)
    into direct_children_quantity
  from public.production_batches
  where parent_batch_id = new.id;
  if direct_children_quantity > new.quantity_started then
    raise exception 'Batch quantity cannot be reduced below quantities already allocated to child batches';
  end if;

  new.part_id := inward_row.part_id;
  new.heat_number := inward_row.heat_number;
  new.heat_code := inward_row.heat_code;
  return new;
end;
$$;

drop trigger if exists trg_batch_genealogy on public.production_batches;
create trigger trg_batch_genealogy
before insert or update of inward_lot_id, parent_batch_id, part_id, heat_number, heat_code, quantity_started
on public.production_batches
for each row execute function public.enforce_batch_genealogy();

create or replace function public.enforce_osp_genealogy()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  source_row public.production_batches%rowtype;
  child_row public.production_batches%rowtype;
  vendor_row public.parties%rowtype;
  process_row public.processes%rowtype;
begin
  select * into source_row from public.production_batches where id = new.source_batch_id;
  select * into child_row from public.production_batches where id = new.osp_batch_id;
  select * into vendor_row from public.parties where id = new.vendor_id;
  select * into process_row from public.processes where id = new.process_id;
  if source_row.id is null or child_row.id is null then
    raise exception 'Source and OSP child batches are required';
  end if;
  if source_row.tenant_id <> new.tenant_id or child_row.tenant_id <> new.tenant_id then
    raise exception 'OSP batch tenant mismatch';
  end if;
  if child_row.parent_batch_id <> source_row.id then
    raise exception 'OSP batch must be a child of the dispatched source batch';
  end if;
  if child_row.inward_lot_id <> source_row.inward_lot_id or child_row.heat_number <> source_row.heat_number or child_row.heat_code <> source_row.heat_code then
    raise exception 'OSP child batch heat genealogy mismatch';
  end if;
  if child_row.quantity_started <> new.quantity_dispatched then
    raise exception 'OSP child batch quantity must equal the dispatched quantity';
  end if;
  if vendor_row.id is null or vendor_row.tenant_id <> new.tenant_id
     or not ('OSP_VENDOR' = any(vendor_row.party_types))
     or coalesce(vendor_row.approval_status, '') <> 'APPROVED'
     or coalesce(vendor_row.status, '') <> 'ACTIVE' then
    raise exception 'OSP dispatch requires an active approved OSP vendor';
  end if;
  if process_row.id is null or process_row.tenant_id <> new.tenant_id
     or process_row.process_type <> 'OUTSOURCED'
     or coalesce(process_row.status, '') <> 'ACTIVE' then
    raise exception 'OSP dispatch requires an active outsourced process';
  end if;
  new.part_id := source_row.part_id;
  return new;
end;
$$;

drop trigger if exists trg_osp_genealogy on public.osp_jobs;
create trigger trg_osp_genealogy
before insert or update of source_batch_id, osp_batch_id, part_id, vendor_id, process_id, quantity_dispatched
on public.osp_jobs
for each row execute function public.enforce_osp_genealogy();

commit;
