-- QSMS calibration, audits, dispatch and documents
begin;

-- -----------------------------------------------------------------------------
-- Calibration, audits, dispatch and document packages
-- -----------------------------------------------------------------------------
create table if not exists public.calibration_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  asset_id uuid not null references public.quality_assets(id),
  certificate_number text not null,
  calibration_date date not null,
  next_due_date date not null,
  agency text not null,
  traceability_reference text,
  result text not null,
  as_found text,
  as_left text,
  measurement_uncertainty text,
  out_of_tolerance_action text,
  status text not null default 'APPROVED',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, certificate_number)
);

create table if not exists public.audit_plans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  audit_number text not null,
  audit_type text not null,
  scope_type text not null,
  party_id uuid references public.parties(id),
  planned_date date not null,
  actual_date date,
  lead_auditor text not null,
  audit_team text,
  scope text,
  standard_reference text,
  opening_time text,
  closing_time text,
  summary text,
  findings_open integer not null default 0,
  status text not null default 'PLANNED',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, audit_number)
);

create table if not exists public.audit_findings (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  audit_plan_id uuid not null references public.audit_plans(id) on delete cascade,
  finding_number text not null,
  classification text not null,
  requirement_reference text,
  finding_text text not null,
  owner text not null,
  target_date date,
  containment text,
  root_cause text,
  corrective_action text,
  implementation_date date,
  effectiveness_verification text,
  verified_by text,
  status text not null default 'OPEN',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (audit_plan_id, finding_number)
);

create table if not exists public.dispatches (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  dispatch_number text not null,
  dispatch_date date not null,
  customer_id uuid not null references public.parties(id),
  invoice_number text not null,
  destination text,
  quality_release_reference text not null,
  quality_release_approved_by text not null,
  status text not null default 'DISPATCHED',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, dispatch_number),
  unique (tenant_id, invoice_number)
);

create table if not exists public.dispatch_batches (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  dispatch_id uuid not null references public.dispatches(id) on delete cascade,
  batch_id uuid not null references public.production_batches(id),
  release_inspection_id uuid not null references public.inspection_reports(id),
  quantity numeric not null check (quantity > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (dispatch_id, batch_id)
);

-- Customer dispatch guard: every dispatched batch quantity must reference an
-- approved passing final inspection/dock audit and must remain within the batch balance.
create or replace function public.enforce_dispatch_batch_release()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  dispatch_row public.dispatches%rowtype;
  batch_row public.production_batches%rowtype;
  inspection_row public.inspection_reports%rowtype;
  part_row public.parts%rowtype;
  prior_dispatched numeric;
  child_allocated numeric;
  available_for_line numeric;
begin
  select * into dispatch_row from public.dispatches where id = new.dispatch_id;
  select * into batch_row from public.production_batches where id = new.batch_id;
  select * into inspection_row from public.inspection_reports where id = new.release_inspection_id;
  if dispatch_row.id is null or batch_row.id is null or inspection_row.id is null then
    raise exception 'Dispatch, batch and approved release inspection are required';
  end if;
  if dispatch_row.tenant_id <> new.tenant_id or batch_row.tenant_id <> new.tenant_id or inspection_row.tenant_id <> new.tenant_id then
    raise exception 'Dispatch batch tenant mismatch';
  end if;
  if inspection_row.batch_id <> batch_row.id
     or upper(inspection_row.report_type) not in ('FINAL_INSPECTION','DOCK_AUDIT','FINAL')
     or inspection_row.overall_result <> 'PASS'
     or inspection_row.status <> 'APPROVED' then
    raise exception 'Dispatch requires an approved PASS final inspection or dock audit linked to the batch';
  end if;
  if inspection_row.inspection_date > dispatch_row.dispatch_date then
    raise exception 'Release inspection cannot be dated after the dispatch';
  end if;
  select * into part_row from public.parts where id = batch_row.part_id;
  if part_row.customer_id is not null and part_row.customer_id <> dispatch_row.customer_id then
    raise exception 'Dispatch customer does not match the batch part customer';
  end if;
  if batch_row.status in ('REJECTED','HOLD','SCRAPPED','HOLD_PENDING_OSP_INSPECTION','AT_OSP') then
    raise exception 'Batch status does not permit customer dispatch';
  end if;
  available_for_line := batch_row.quantity_available;
  if tg_op = 'UPDATE' and new.batch_id = old.batch_id then
    available_for_line := available_for_line + old.quantity;
  end if;
  if new.quantity > available_for_line then
    raise exception 'Dispatch quantity exceeds current batch availability';
  end if;
  select coalesce(sum(quantity), 0)
    into prior_dispatched
  from public.dispatch_batches
  where batch_id = batch_row.id
    and (new.id is null or id <> new.id);
  select coalesce(sum(quantity_started), 0)
    into child_allocated
  from public.production_batches
  where parent_batch_id = batch_row.id;
  if prior_dispatched + child_allocated + new.quantity > batch_row.quantity_started then
    raise exception 'Cumulative child allocation and dispatch exceed the batch quantity';
  end if;
  return new;
end;
$$;

revoke all on function public.enforce_dispatch_batch_release() from public, anon, authenticated;

drop trigger if exists trg_dispatch_batch_release on public.dispatch_batches;
create trigger trg_dispatch_batch_release
before insert or update of dispatch_id, batch_id, release_inspection_id, quantity
on public.dispatch_batches
for each row execute function public.enforce_dispatch_batch_release();

-- Keep batch availability synchronized when a dispatch line is inserted,
-- corrected or deleted. The Streamlit update is idempotent with this trigger.
create or replace function public.apply_dispatch_batch_quantity()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  delta numeric;
  target_batch uuid;
begin
  if tg_op = 'INSERT' then
    delta := new.quantity;
    target_batch := new.batch_id;
  elsif tg_op = 'UPDATE' then
    if new.batch_id <> old.batch_id then
      update public.production_batches
      set quantity_available = least(quantity_started, quantity_available + old.quantity),
          status = case
            when least(quantity_started, quantity_available + old.quantity) > 0 and status = 'DISPATCHED' then 'IN_PROCESS'
            else status
          end
      where id = old.batch_id;
      delta := new.quantity;
      target_batch := new.batch_id;
    else
      delta := new.quantity - old.quantity;
      target_batch := new.batch_id;
    end if;
  else
    update public.production_batches
    set quantity_available = least(quantity_started, quantity_available + old.quantity),
        status = case when status = 'DISPATCHED' then 'IN_PROCESS' else status end
    where id = old.batch_id;
    return old;
  end if;

  update public.production_batches
  set quantity_available = greatest(0, quantity_available - delta),
      status = case
        when greatest(0, quantity_available - delta) = 0 then 'DISPATCHED'
        when status = 'DISPATCHED' then 'IN_PROCESS'
        else status
      end
  where id = target_batch;
  return new;
end;
$$;

revoke all on function public.apply_dispatch_batch_quantity() from public, anon, authenticated;

drop trigger if exists trg_apply_dispatch_batch_quantity on public.dispatch_batches;
create trigger trg_apply_dispatch_batch_quantity
after insert or update or delete on public.dispatch_batches
for each row execute function public.apply_dispatch_batch_quantity();

-- Atomic customer dispatch transaction. The header, released batch quantity and
-- genealogy movement either all succeed or all roll back together.
create or replace function public.create_traceable_dispatch(
  p_dispatch_number text,
  p_dispatch_date date,
  p_customer_id uuid,
  p_invoice_number text,
  p_destination text,
  p_release_inspection_id uuid,
  p_quality_release_approved_by text,
  p_batch_id uuid,
  p_quantity numeric,
  p_remarks text
)
returns uuid
language plpgsql
security invoker
set search_path = public, auth
as $$
declare
  tenant_key uuid := public.current_tenant_id();
  dispatch_key uuid;
  release_reference text;
  process_key uuid;
begin
  if tenant_key is null then
    raise exception 'Authenticated tenant context is required';
  end if;
  if nullif(btrim(coalesce(p_dispatch_number, '')), '') is null
     or nullif(btrim(coalesce(p_invoice_number, '')), '') is null
     or nullif(btrim(coalesce(p_quality_release_approved_by, '')), '') is null then
    raise exception 'Dispatch number, invoice number and quality approver are required';
  end if;
  if p_dispatch_date is null or p_quantity is null or p_quantity <= 0 then
    raise exception 'Dispatch date and positive quantity are required';
  end if;
  if not exists (
    select 1
    from public.parties customer
    where customer.id = p_customer_id
      and customer.tenant_id = tenant_key
      and 'CUSTOMER' = any(customer.party_types)
      and customer.status = 'ACTIVE'
  ) then
    raise exception 'An active customer is required';
  end if;

  select report_number
    into release_reference
  from public.inspection_reports
  where id = p_release_inspection_id
    and tenant_id = tenant_key;
  if release_reference is null then
    raise exception 'The selected release inspection is not available in the active tenant';
  end if;

  insert into public.dispatches (
    tenant_id, dispatch_number, dispatch_date, customer_id, invoice_number,
    destination, quality_release_reference, quality_release_approved_by,
    status, remarks
  ) values (
    tenant_key, btrim(p_dispatch_number), p_dispatch_date, p_customer_id,
    btrim(p_invoice_number), nullif(btrim(coalesce(p_destination, '')), ''),
    release_reference, btrim(p_quality_release_approved_by), 'DISPATCHED',
    nullif(btrim(coalesce(p_remarks, '')), '')
  ) returning id into dispatch_key;

  insert into public.dispatch_batches (
    tenant_id, dispatch_id, batch_id, release_inspection_id, quantity
  ) values (
    tenant_key, dispatch_key, p_batch_id, p_release_inspection_id, p_quantity
  );

  select current_process_id
    into process_key
  from public.production_batches
  where id = p_batch_id and tenant_id = tenant_key;

  insert into public.batch_movements (
    tenant_id, batch_id, movement_type, from_process_id, to_process_id,
    quantity, movement_date, reference, remarks
  ) values (
    tenant_key, p_batch_id, 'CUSTOMER_DISPATCH', process_key, null,
    p_quantity, p_dispatch_date, btrim(p_invoice_number),
    concat('Dispatch ', btrim(p_dispatch_number),
           case when nullif(btrim(coalesce(p_remarks, '')), '') is null
                then '' else concat(' · ', btrim(p_remarks)) end)
  );

  return dispatch_key;
end;
$$;

revoke all on function public.create_traceable_dispatch(text,date,uuid,text,text,uuid,text,uuid,numeric,text) from public, anon;
grant execute on function public.create_traceable_dispatch(text,date,uuid,text,text,uuid,text,uuid,numeric,text) to authenticated;

create table if not exists public.customer_report_packages (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  package_number text not null,
  customer_id uuid not null references public.parties(id),
  part_id uuid not null references public.parts(id),
  batch_id uuid not null references public.production_batches(id),
  dispatch_id uuid references public.dispatches(id),
  prepared_date date not null,
  sent_date date,
  sent_to text,
  status text not null default 'PREPARED',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, package_number)
);

create table if not exists public.customer_report_package_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  package_id uuid not null references public.customer_report_packages(id) on delete cascade,
  document_type text not null,
  reference text,
  document_date date,
  status text,
  entity_type text,
  entity_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.standards_register (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  standard_code text not null,
  edition text not null,
  document_owner text not null,
  review_due_date date,
  status text not null default 'CURRENT',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, standard_code, edition)
);

create table if not exists public.document_attachments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  entity_type text not null,
  entity_id uuid not null,
  document_type text not null,
  file_name text not null,
  object_path text not null,
  mime_type text,
  size_bytes bigint,
  checksum text,
  revision text,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, object_path)
);

create table if not exists public.document_approvals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  entity_type text not null,
  entity_id uuid not null,
  approval_action text not null,
  status_from text,
  status_to text,
  comments text,
  approved_by uuid references public.profiles(id),
  approved_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.number_sequences (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  sequence_code text not null,
  prefix text not null,
  year_format text default 'YYYY',
  current_value bigint not null default 0,
  padding integer not null default 5,
  reset_frequency text default 'YEARLY',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, sequence_code)
);

create table if not exists public.audit_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id),
  table_name text not null,
  row_id uuid,
  operation text not null,
  old_data jsonb,
  new_data jsonb,
  changed_by uuid,
  changed_at timestamptz not null default now()
);

create or replace function public.log_row_change()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  payload jsonb;
  prior jsonb;
  tid uuid;
  rid uuid;
begin
  if tg_op = 'DELETE' then
    payload := to_jsonb(old);
    prior := to_jsonb(old);
  elsif tg_op = 'INSERT' then
    payload := to_jsonb(new);
    prior := null;
  else
    payload := to_jsonb(new);
    prior := to_jsonb(old);
  end if;
  begin
    tid := nullif(payload->>'tenant_id','')::uuid;
  exception when others then
    tid := public.current_tenant_id();
  end;
  begin
    rid := nullif(payload->>'id','')::uuid;
  exception when others then
    rid := null;
  end;
  insert into public.audit_log (tenant_id, table_name, row_id, operation, old_data, new_data, changed_by)
  values (tid, tg_table_name, rid, tg_op, prior, case when tg_op = 'DELETE' then null else payload end, auth.uid());
  if tg_op = 'DELETE' then return old; else return new; end if;
end;
$$;

commit;
