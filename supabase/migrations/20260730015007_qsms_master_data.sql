-- QSMS master data
begin;

-- -----------------------------------------------------------------------------
-- Master data
-- -----------------------------------------------------------------------------
create table if not exists public.parties (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  party_code text not null,
  party_name text not null,
  party_types text[] not null default '{}'::text[],
  country text,
  state text,
  city text,
  address text,
  contact_person text,
  email text,
  phone text,
  tax_identifier text,
  approval_status text default 'APPROVED',
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, party_code)
);

create table if not exists public.material_grades (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  grade_code text not null,
  standard text,
  revision text,
  effective_date date,
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, grade_code, revision)
);

create table if not exists public.material_grade_elements (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  material_grade_id uuid not null references public.material_grades(id) on delete cascade,
  element text not null,
  minimum numeric,
  maximum numeric,
  unit text not null default '%',
  test_method text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  check (minimum is null or maximum is null or minimum <= maximum),
  unique (material_grade_id, element)
);

create table if not exists public.parts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_number text not null,
  part_name text not null,
  customer_id uuid references public.parties(id),
  material_grade_id uuid references public.material_grades(id),
  drawing_number text,
  drawing_revision text,
  finished_weight_kg numeric,
  forging_weight_kg numeric,
  gross_weight_kg numeric,
  section_size text,
  manufacturing_route text,
  special_characteristics jsonb not null default '[]'::jsonb,
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, part_number)
);

create table if not exists public.part_supplier_links (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id) on delete cascade,
  supplier_id uuid not null references public.parties(id),
  steel_mill_id uuid references public.parties(id),
  supplier_part_number text,
  approval_reference text,
  approved boolean not null default true,
  valid_from date,
  valid_to date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, part_id, supplier_id, steel_mill_id)
);

create table if not exists public.processes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  process_code text not null,
  process_name text not null,
  process_type text not null default 'IN_HOUSE' check (process_type in ('IN_HOUSE','OUTSOURCED')),
  special_process boolean not null default false,
  cqi_standard text,
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, process_code)
);

create table if not exists public.inspection_stages (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  stage_code text not null,
  stage_name text not null,
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, stage_code)
);

create table if not exists public.quality_assets (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  asset_code text not null,
  asset_name text not null,
  asset_type text not null check (asset_type in ('INSTRUMENT','EQUIPMENT','GAUGE','FIXTURE','JIG','MASTER','REFERENCE_STANDARD')),
  manufacturer text,
  model text,
  serial_number text,
  range_text text,
  least_count text,
  location text,
  calibration_frequency_days integer not null default 365 check (calibration_frequency_days > 0),
  last_calibration_date date,
  next_due_date date,
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, asset_code)
);

-- Part-wise inspection and test planning
create table if not exists public.inspection_plans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id),
  process_id uuid references public.processes(id),
  inspection_stage_id uuid references public.inspection_stages(id),
  plan_number text not null,
  revision text not null default '00',
  effective_date date,
  sample_plan text,
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, plan_number, revision)
);

create table if not exists public.inspection_plan_characteristics (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  inspection_plan_id uuid not null references public.inspection_plans(id) on delete cascade,
  sequence_no integer not null,
  characteristic_no text,
  characteristic text not null,
  specification text,
  lower_spec numeric,
  upper_spec numeric,
  unit text,
  characteristic_type text default 'VARIABLE',
  special_class text,
  checking_aid_id uuid references public.quality_assets(id),
  checking_method text,
  sample_size integer,
  frequency text,
  reaction_plan text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (inspection_plan_id, sequence_no)
);

create table if not exists public.test_plans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id),
  process_id uuid references public.processes(id),
  inspection_stage_id uuid references public.inspection_stages(id),
  plan_number text not null,
  revision text not null default '00',
  test_type text not null,
  specification_reference text,
  frequency text,
  sample_size integer,
  acceptance_criteria jsonb not null default '{}'::jsonb,
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, plan_number, revision)
);

commit;
