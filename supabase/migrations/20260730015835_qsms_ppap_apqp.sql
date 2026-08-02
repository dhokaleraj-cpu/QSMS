-- QSMS PPAP and APQP
begin;

-- -----------------------------------------------------------------------------
-- PPAP / APQP
-- -----------------------------------------------------------------------------
create table if not exists public.ppap_projects (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  project_code text not null,
  part_id uuid not null references public.parts(id),
  customer_id uuid not null references public.parties(id),
  submission_level text,
  reason text,
  target_submission_date date,
  coordinator text,
  completion_percent numeric not null default 0 check (completion_percent between 0 and 100),
  status text not null default 'IN_PROGRESS',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, project_code)
);

create table if not exists public.ppap_documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid not null references public.ppap_projects(id) on delete cascade,
  document_type text not null,
  document_number text,
  revision text,
  owner text,
  due_date date,
  approved_date date,
  status text not null default 'NOT_STARTED',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.pfd_headers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid not null references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  document_number text not null,
  revision text not null,
  effective_date date,
  core_team text,
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, document_number, revision)
);

create table if not exists public.pfd_steps (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  pfd_header_id uuid not null references public.pfd_headers(id) on delete cascade,
  step_no integer not null,
  step_type text,
  location_type text,
  process_operation text not null,
  product_characteristic text,
  process_characteristic text,
  control_verification text,
  responsible text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (pfd_header_id, step_no)
);

create table if not exists public.pfmea_headers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid not null references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  document_number text not null,
  revision text not null,
  effective_date date,
  methodology text not null default 'LEGACY_RPN' check (methodology in ('LEGACY_RPN','AIAG_VDA')),
  core_team text,
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, document_number, revision)
);

create table if not exists public.pfmea_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  pfmea_header_id uuid not null references public.pfmea_headers(id) on delete cascade,
  line_no integer not null,
  process_step_function text,
  failure_mode text not null,
  failure_effect text,
  severity integer check (severity between 1 and 10),
  special_characteristic text,
  failure_cause text,
  prevention_control text,
  occurrence integer check (occurrence between 1 and 10),
  detection_control text,
  detection integer check (detection between 1 and 10),
  rpn integer,
  action_priority text,
  recommended_action text,
  responsible_due text,
  action_taken text,
  revised_severity integer check (revised_severity between 1 and 10),
  revised_occurrence integer check (revised_occurrence between 1 and 10),
  revised_detection integer check (revised_detection between 1 and 10),
  revised_rpn integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (pfmea_header_id, line_no)
);

create table if not exists public.control_plan_headers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid not null references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  document_number text not null,
  revision text not null,
  effective_date date,
  plan_type text,
  core_team text,
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, document_number, revision)
);

create table if not exists public.control_plan_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  control_plan_header_id uuid not null references public.control_plan_headers(id) on delete cascade,
  line_no integer not null,
  process_no integer,
  process_operation text not null,
  machine_equipment text,
  characteristic_no text,
  product_characteristic text,
  process_characteristic text,
  special_class text,
  specification_tolerance text,
  measurement_technique text,
  sample_size text,
  frequency text,
  control_method_responsibility text,
  reaction_plan text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (control_plan_header_id, line_no)
);

create table if not exists public.spc_plans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  study_number text not null,
  characteristic text not null,
  measurement_method text,
  target numeric,
  lower_spec numeric,
  upper_spec numeric,
  acceptance_cpk numeric default 1.33,
  subgroup_size integer,
  frequency text,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, study_number)
);

create table if not exists public.spc_studies (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  spc_plan_id uuid not null references public.spc_plans(id) on delete cascade,
  study_date date not null,
  sample_size integer not null,
  results jsonb not null,
  overall_result text not null,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.spc_readings (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  spc_study_id uuid not null references public.spc_studies(id) on delete cascade,
  sequence_no integer not null,
  subgroup_no integer,
  value numeric not null,
  measured_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (spc_study_id, sequence_no)
);

create table if not exists public.msa_plans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  study_number text not null,
  characteristic text not null,
  study_type text not null,
  appraisers integer,
  parts_count integer,
  trials integer,
  method_reference text not null,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, study_number)
);

create table if not exists public.msa_studies (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  msa_plan_id uuid not null references public.msa_plans(id) on delete cascade,
  study_date date not null,
  results jsonb not null default '{}'::jsonb,
  observations text,
  overall_result text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.msa_readings (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  msa_study_id uuid not null references public.msa_studies(id) on delete cascade,
  appraiser text,
  part_no integer,
  trial_no integer,
  value numeric,
  attribute_result text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.capacity_studies (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  study_number text not null,
  phase text,
  process_operation text not null,
  study_date date,
  inputs jsonb not null,
  results jsonb not null,
  overall_result text not null,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, study_number)
);

create table if not exists public.balloon_characteristics (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  ppap_project_id uuid references public.ppap_projects(id) on delete cascade,
  part_id uuid not null references public.parts(id),
  drawing_number text not null,
  drawing_revision text not null,
  balloon_no integer not null,
  drawing_zone text,
  characteristic text not null,
  specification_tolerance text,
  characteristic_type text,
  special_class text,
  measurement_method text,
  inspection_report_link text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, drawing_number, drawing_revision, balloon_no)
);

commit;
