-- QCMS 4.9.7 — Process Flow Designer, NPD Order Status and APQP tracking
begin;

create table if not exists public.npd_process_flows (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id),
  revision text not null default 'A',
  effective_date date,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','DRAFT','INACTIVE')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, part_id)
);

create table if not exists public.npd_process_flow_steps (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  flow_id uuid not null references public.npd_process_flows(id) on delete cascade,
  process_id uuid not null references public.processes(id),
  operation_no integer not null check (operation_no >= 0),
  process_name_snapshot text not null,
  target_lead_days integer not null default 0 check (target_lead_days >= 0),
  responsible text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (flow_id, operation_no)
);

create table if not exists public.npd_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  order_number text not null,
  part_id uuid not null references public.parts(id),
  customer_id uuid not null references public.parties(id),
  order_qty numeric not null check (order_qty > 0),
  order_date date not null default current_date,
  start_date date not null default current_date,
  delivery_date date not null,
  status text not null default 'OPEN' check (status in ('OPEN','IN_PROGRESS','ON_HOLD','COMPLETED','CANCELLED')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, order_number)
);

create table if not exists public.npd_order_steps (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  npd_order_id uuid not null references public.npd_orders(id) on delete cascade,
  flow_step_id uuid references public.npd_process_flow_steps(id) on delete set null,
  operation_no integer not null,
  process_id uuid references public.processes(id),
  process_name text not null,
  target_date date,
  status text not null default 'PENDING' check (status in ('PENDING','IN_PROGRESS','ON_HOLD','COMPLETED')),
  completed_date date,
  responsible text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (npd_order_id, operation_no)
);

alter table public.ppap_documents add column if not exists apqp_phase text;
alter table public.ppap_documents add column if not exists sequence_no integer;

create index if not exists idx_npd_flow_part on public.npd_process_flows(tenant_id, part_id);
create index if not exists idx_npd_flow_steps on public.npd_process_flow_steps(flow_id, operation_no);
create index if not exists idx_npd_orders_due on public.npd_orders(tenant_id, delivery_date, status);
create index if not exists idx_npd_orders_part on public.npd_orders(tenant_id, part_id, customer_id);
create index if not exists idx_npd_order_steps_status on public.npd_order_steps(npd_order_id, operation_no, status, target_date);
create index if not exists idx_ppap_documents_sequence on public.ppap_documents(ppap_project_id, sequence_no);

-- Route all NPD / APQP data through one configurable module permission.
create or replace function public.qsms_module_for_table(target_table text) returns text language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table in ('npd_process_flows','npd_process_flow_steps','npd_orders','npd_order_steps','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then 'NPD_APQP'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','processes','inspection_stages','master_value_catalog') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
 elsif target_table in ('employees','quality_assets') then return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
 elsif target_table='inward_lots' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('production_batches','batch_movements','osp_jobs') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA');
 elsif target_table in ('inspection_reports','inspection_results') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
 elsif target_table='lab_tests' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
 elsif target_table in ('npd_process_flows','npd_process_flow_steps','npd_orders','npd_order_steps','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION');
 end if;
 return false;
end;
$$;

-- Updated-at and audit triggers for the new controlled transaction tables.
do $$
declare table_name text;
begin
 foreach table_name in array array['npd_process_flows','npd_process_flow_steps','npd_orders','npd_order_steps'] loop
  execute format('drop trigger if exists trg_touch_updated_at on public.%I', table_name);
  execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', table_name);
  execute format('drop trigger if exists trg_audit_row_change on public.%I', table_name);
  execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()', table_name);
 end loop;
end;
$$;

-- Tenant RLS. NPD planners with module write permission can maintain the flow and order tracker.
do $$
declare table_name text;
begin
 foreach table_name in array array['npd_process_flows','npd_process_flow_steps','npd_orders','npd_order_steps'] loop
  execute format('alter table public.%I enable row level security', table_name);
  execute format('drop policy if exists tenant_select on public.%I', table_name);
  execute format('drop policy if exists tenant_insert on public.%I', table_name);
  execute format('drop policy if exists tenant_update on public.%I', table_name);
  execute format('drop policy if exists tenant_delete on public.%I', table_name);
  execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id=public.current_tenant_id())', table_name);
  execute format('create policy tenant_insert on public.%I for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
  execute format('create policy tenant_update on public.%I for update to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L)) with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name, table_name);
  execute format('create policy tenant_delete on public.%I for delete to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
 end loop;
end;
$$;

-- APQP tables already exist; refresh their RLS policies to use the new NPD_APQP module permission.
do $$
declare table_name text;
begin
 foreach table_name in array array['ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics'] loop
  execute format('alter table public.%I enable row level security', table_name);
  execute format('drop policy if exists tenant_select on public.%I', table_name);
  execute format('drop policy if exists tenant_insert on public.%I', table_name);
  execute format('drop policy if exists tenant_update on public.%I', table_name);
  execute format('drop policy if exists tenant_delete on public.%I', table_name);
  execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id=public.current_tenant_id())', table_name);
  execute format('create policy tenant_insert on public.%I for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
  execute format('create policy tenant_update on public.%I for update to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L)) with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name, table_name);
  execute format('create policy tenant_delete on public.%I for delete to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
 end loop;
end;
$$;

commit;
