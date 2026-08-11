-- QCMS 4.9.8 - normalized duplicate guards, NPD process checkpoints, employee responsibility and QC calculation records
begin;

-- Employee-linked responsibility fields preserve the old text snapshots for backward compatibility.
alter table public.npd_process_flow_steps add column if not exists responsible_employee_id uuid references public.employees(id) on delete set null;
alter table public.npd_order_steps add column if not exists responsible_employee_id uuid references public.employees(id) on delete set null;
alter table public.ppap_projects add column if not exists coordinator_employee_id uuid references public.employees(id) on delete set null;
alter table public.ppap_documents add column if not exists owner_employee_id uuid references public.employees(id) on delete set null;

create table if not exists public.npd_process_flow_points (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  flow_step_id uuid not null references public.npd_process_flow_steps(id) on delete cascade,
  sequence_no integer not null default 10,
  point_text text not null,
  responsible_employee_id uuid references public.employees(id) on delete set null,
  responsible_snapshot text,
  remarks text,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (flow_step_id, sequence_no)
);

create table if not exists public.npd_order_step_points (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  npd_order_step_id uuid not null references public.npd_order_steps(id) on delete cascade,
  flow_point_id uuid references public.npd_process_flow_points(id) on delete set null,
  sequence_no integer not null default 10,
  point_text text not null,
  responsible_employee_id uuid references public.employees(id) on delete set null,
  responsible_snapshot text,
  target_date date,
  status text not null default 'PENDING' check (status in ('PENDING','IN_PROGRESS','COMPLETED','NOT_APPLICABLE','ON_HOLD')),
  completed_date date,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (npd_order_step_id, sequence_no)
);

create table if not exists public.qc_calculation_records (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  calculation_number text not null,
  calculation_type text not null check (calculation_type in ('JOMINY','DI_VALUE','HARDNESS_CONVERSION')),
  calculation_date date not null default current_date,
  part_id uuid references public.parts(id) on delete set null,
  material_grade_id uuid references public.material_grades(id) on delete set null,
  heat_number text,
  primary_unit text,
  primary_value numeric,
  conversion_unit text,
  result_value numeric,
  input_payload jsonb not null default '{}'::jsonb,
  result_payload jsonb not null default '{}'::jsonb,
  standard_reference text,
  performed_by_employee_id uuid references public.employees(id) on delete set null,
  remarks text,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','VOID')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, calculation_number)
);

create index if not exists idx_npd_flow_points_step on public.npd_process_flow_points(flow_step_id, sequence_no);
create index if not exists idx_npd_order_points_step on public.npd_order_step_points(npd_order_step_id, sequence_no, status);
create index if not exists idx_qc_calculation_records_type_date on public.qc_calculation_records(tenant_id, calculation_type, calculation_date desc);
create index if not exists idx_qc_calculation_records_part on public.qc_calculation_records(tenant_id, part_id, heat_number);

-- Guard new/changed Process and Inspection Stage codes/names case-insensitively.
-- Existing historical duplicates are grandfathered until edited, avoiding destructive merges.
create or replace function public.qcms_guard_process_duplicates() returns trigger
language plpgsql set search_path=public as $$
begin
  if tg_op='INSERT' or lower(btrim(coalesce(new.process_code,''))) is distinct from lower(btrim(coalesce(old.process_code,''))) then
    if exists(select 1 from public.processes p where p.tenant_id=new.tenant_id and p.id<>new.id and lower(btrim(p.process_code))=lower(btrim(new.process_code))) then
      raise exception 'Duplicate Process Code is not allowed.';
    end if;
  end if;
  if tg_op='INSERT' or lower(btrim(coalesce(new.process_name,''))) is distinct from lower(btrim(coalesce(old.process_name,''))) then
    if exists(select 1 from public.processes p where p.tenant_id=new.tenant_id and p.id<>new.id and lower(btrim(p.process_name))=lower(btrim(new.process_name))) then
      raise exception 'Duplicate Process Name is not allowed.';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_qcms_process_duplicate_guard on public.processes;
create trigger trg_qcms_process_duplicate_guard before insert or update of process_code,process_name on public.processes
for each row execute function public.qcms_guard_process_duplicates();

create or replace function public.qcms_guard_stage_duplicates() returns trigger
language plpgsql set search_path=public as $$
begin
  if tg_op='INSERT' or lower(btrim(coalesce(new.stage_code,''))) is distinct from lower(btrim(coalesce(old.stage_code,''))) then
    if exists(select 1 from public.inspection_stages s where s.tenant_id=new.tenant_id and s.id<>new.id and lower(btrim(s.stage_code))=lower(btrim(new.stage_code))) then
      raise exception 'Duplicate Inspection Stage Code is not allowed.';
    end if;
  end if;
  if tg_op='INSERT' or lower(btrim(coalesce(new.stage_name,''))) is distinct from lower(btrim(coalesce(old.stage_name,''))) then
    if exists(select 1 from public.inspection_stages s where s.tenant_id=new.tenant_id and s.id<>new.id and lower(btrim(s.stage_name))=lower(btrim(new.stage_name))) then
      raise exception 'Duplicate Inspection Stage Name is not allowed.';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_qcms_stage_duplicate_guard on public.inspection_stages;
create trigger trg_qcms_stage_duplicate_guard before insert or update of stage_code,stage_name on public.inspection_stages
for each row execute function public.qcms_guard_stage_duplicates();

-- Route new controlled tables through configurable application permissions.
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
 when target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then 'NPD_APQP'
 when target_table='qc_calculation_records' then 'QC_CALCULATION_TOOLS'
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
 elsif target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION');
 elsif target_table='qc_calculation_records' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA');
 end if;
 return false;
end;
$$;

-- Updated-at/audit/RLS for new controlled tables.
do $$
declare table_name text;
begin
 foreach table_name in array array['npd_process_flow_points','npd_order_step_points','qc_calculation_records'] loop
  execute format('drop trigger if exists trg_touch_updated_at on public.%I', table_name);
  execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', table_name);
  execute format('drop trigger if exists trg_audit_row_change on public.%I', table_name);
  execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()', table_name);
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
