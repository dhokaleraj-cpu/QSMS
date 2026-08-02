-- QSMS inspection and laboratory
begin;

-- -----------------------------------------------------------------------------
-- Inspection and laboratory
-- -----------------------------------------------------------------------------
create table if not exists public.inspection_reports (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  report_number text not null,
  report_type text not null,
  inspection_plan_id uuid references public.inspection_plans(id),
  inspection_stage_id uuid references public.inspection_stages(id),
  part_id uuid not null references public.parts(id),
  batch_id uuid references public.production_batches(id),
  inward_lot_id uuid references public.inward_lots(id),
  osp_job_id uuid references public.osp_jobs(id),
  inspection_date date not null,
  sample_size integer not null default 1 check (sample_size > 0),
  accepted_quantity numeric not null default 0,
  rejected_quantity numeric not null default 0,
  inspector text,
  overall_result text not null check (overall_result in ('PASS','FAIL','HOLD','NOT_EVALUATED')),
  status text not null default 'DRAFT',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, report_number)
);

create table if not exists public.inspection_results (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  inspection_report_id uuid not null references public.inspection_reports(id) on delete cascade,
  inspection_plan_characteristic_id uuid references public.inspection_plan_characteristics(id),
  characteristic_no text,
  characteristic text not null,
  specification text,
  lower_spec numeric,
  upper_spec numeric,
  checking_aid text,
  checking_aid_id uuid references public.quality_assets(id),
  observations jsonb not null default '[]'::jsonb,
  attribute_result text,
  result text not null,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.lab_tests (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  report_number text not null,
  test_type text not null,
  test_plan_id uuid references public.test_plans(id),
  part_id uuid not null references public.parts(id),
  batch_id uuid references public.production_batches(id),
  inward_lot_id uuid references public.inward_lots(id),
  osp_job_id uuid references public.osp_jobs(id),
  test_date date not null,
  sample_reference text not null,
  specification_reference text,
  results jsonb not null default '{}'::jsonb,
  overall_result text not null,
  status text not null default 'DRAFT',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, report_number)
);

-- OSP quality gate: a received job cannot be marked released/completed until
-- every required inspection/test has an approved PASS record linked to the job.
create or replace function public.enforce_osp_quality_release()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  missing_checks text[];
begin
  if new.status = 'COMPLETED' or new.inspection_status = 'PASS' then
    if new.quantity_received <= 0 then
      raise exception 'OSP release requires a received quantity';
    end if;
    if new.receipt_status <> 'COMPLETE' or new.quantity_received <> new.quantity_dispatched then
      raise exception 'OSP release requires receipt of the full dispatched quantity';
    end if;
    if nullif(btrim(coalesce(new.vendor_batch_number,'')), '') is null then
      raise exception 'OSP release requires the vendor/furnace batch code';
    end if;

    select array_agg(required_check order by required_check)
      into missing_checks
    from unnest(coalesce(new.required_tests, '{}'::text[])) as required_check
    where not exists (
      select 1
      from public.inspection_reports inspection
      where inspection.osp_job_id = new.id
        and upper(inspection.report_type) = upper(required_check)
        and inspection.overall_result = 'PASS'
        and inspection.status = 'APPROVED'
      union all
      select 1
      from public.lab_tests test
      where test.osp_job_id = new.id
        and upper(test.test_type) = upper(required_check)
        and test.overall_result = 'PASS'
        and test.status = 'APPROVED'
    );

    if coalesce(cardinality(missing_checks), 0) > 0 then
      raise exception 'OSP release blocked; missing approved PASS checks: %', array_to_string(missing_checks, ', ');
    end if;
    new.inspection_status := 'PASS';
    new.status := 'COMPLETED';
  end if;
  return new;
end;
$$;

revoke all on function public.enforce_osp_quality_release() from public, anon, authenticated;

drop trigger if exists trg_osp_quality_release on public.osp_jobs;
create trigger trg_osp_quality_release
before insert or update of status, inspection_status, required_tests, vendor_batch_number, quantity_received
on public.osp_jobs
for each row execute function public.enforce_osp_quality_release();

create table if not exists public.calculation_rules (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  rule_code text not null,
  rule_name text not null,
  test_type text not null,
  revision text not null,
  formula_definition jsonb not null,
  validation_reference text,
  validated_by text,
  validated_at timestamptz,
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, rule_code, revision)
);

commit;
