-- QCMS v4.12.0 - Flexible inspection stages, multi-section raw material details and Supply Chain
-- Additive only: existing transaction IDs and records are preserved.

-- 1) Allow standalone Dimensional / MetLAB reports at controlled business stages.
alter table public.inspection_reports drop constraint if exists inspection_reports_scope_check;
alter table public.inspection_reports add constraint inspection_reports_scope_check check (
  inspection_scope in ('MATERIAL_INWARD','OSP_SAMPLE','OSP_RECEIPT','RAW_MATERIAL_STAGE','OSP_STAGE','FINAL_DISPATCH_STAGE')
);
alter table public.lab_tests drop constraint if exists lab_tests_scope_check;
alter table public.lab_tests add constraint lab_tests_scope_check check (
  inspection_scope in ('MATERIAL_INWARD','OSP_SAMPLE','OSP_RECEIPT','RAW_MATERIAL_STAGE','OSP_STAGE','FINAL_DISPATCH_STAGE')
);

-- 2) Part Master E - Raw Material Details may contain multiple logical material sections.
alter table public.part_raw_material_details
  add column if not exists material_section_name text not null default 'Primary Raw Material';
create index if not exists idx_part_raw_material_details_section
  on public.part_raw_material_details(tenant_id, part_id, material_section_name, sequence_no);

-- 3) End-to-end Supply Chain tables linked by the same customer-order reference.
create table if not exists public.supply_customer_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  master_reference_no text not null,
  order_type text not null check (order_type in ('PURCHASE_ORDER','MONTHLY_SCHEDULE')),
  customer_id uuid not null references public.parties(id),
  part_id uuid not null references public.parts(id),
  customer_order_no text,
  order_position text,
  schedule_month date,
  order_date date not null default current_date,
  customer_delivery_date date,
  order_qty_pcs numeric(18,3) not null check (order_qty_pcs > 0),
  forging_supplier_id uuid not null references public.parties(id),
  raw_material_detail_id uuid not null references public.part_raw_material_details(id),
  gross_weight_kg_snapshot numeric(18,6) not null check (gross_weight_kg_snapshot > 0),
  required_rm_kg numeric(18,3) not null check (required_rm_kg > 0),
  status text not null default 'OPEN' check (status in ('OPEN','IN_PROGRESS','COMPLETED','CANCELLED')),
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id),
  check (
    (order_type='PURCHASE_ORDER' and nullif(btrim(customer_order_no),'') is not null)
    or
    (order_type='MONTHLY_SCHEDULE' and schedule_month is not null)
  )
);
create unique index if not exists uq_supply_customer_order_position
  on public.supply_customer_orders(tenant_id, customer_id, lower(master_reference_no), coalesce(order_position,''))
  where status <> 'CANCELLED';
create unique index if not exists uq_supply_monthly_schedule
  on public.supply_customer_orders(tenant_id, customer_id, part_id, schedule_month)
  where order_type='MONTHLY_SCHEDULE' and status <> 'CANCELLED';
create index if not exists idx_supply_customer_orders_ref on public.supply_customer_orders(tenant_id, lower(master_reference_no));

create table if not exists public.supply_rm_purchase_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  rm_supplier_id uuid not null references public.parties(id),
  supplier_order_no text not null,
  order_date date not null default current_date,
  ordered_qty_kg numeric(18,3) not null check (ordered_qty_kg > 0),
  expected_date date,
  status text not null default 'OPEN' check (status in ('OPEN','PART_RECEIVED','CLOSED','CANCELLED')),
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id)
);
create unique index if not exists uq_supply_rm_po_order_supplier
  on public.supply_rm_purchase_orders(tenant_id, customer_order_id, rm_supplier_id)
  where status <> 'CANCELLED';
create unique index if not exists uq_supply_rm_supplier_order_no
  on public.supply_rm_purchase_orders(tenant_id, rm_supplier_id, lower(supplier_order_no))
  where status <> 'CANCELLED';

create table if not exists public.supply_rm_receipts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  rm_purchase_order_id uuid not null references public.supply_rm_purchase_orders(id) on delete restrict,
  receipt_number text not null,
  receipt_date date not null default current_date,
  heat_number text,
  received_qty_kg numeric(18,3) not null check (received_qty_kg > 0),
  supplier_challan text, remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id)
);
create unique index if not exists uq_supply_rm_receipt_no
  on public.supply_rm_receipts(tenant_id, rm_purchase_order_id, lower(receipt_number));

create table if not exists public.supply_forging_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  forging_supplier_id uuid not null references public.parties(id),
  supplier_order_no text not null,
  order_date date not null default current_date,
  order_qty_pcs numeric(18,3) not null check (order_qty_pcs > 0),
  required_rm_kg numeric(18,3) not null check (required_rm_kg > 0),
  expected_date date,
  status text not null default 'OPEN' check (status in ('OPEN','PART_RECEIVED','CLOSED','CANCELLED')),
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id)
);
create unique index if not exists uq_supply_forging_order_supplier
  on public.supply_forging_orders(tenant_id, customer_order_id, forging_supplier_id)
  where status <> 'CANCELLED';
create unique index if not exists uq_supply_forging_supplier_order_no
  on public.supply_forging_orders(tenant_id, forging_supplier_id, lower(supplier_order_no))
  where status <> 'CANCELLED';

create table if not exists public.supply_rm_dispatches (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  forging_supplier_id uuid not null references public.parties(id),
  dispatch_number text not null,
  dispatch_date date not null default current_date,
  heat_number text,
  qty_kg numeric(18,3) not null check (qty_kg > 0),
  challan_number text, vehicle_number text, remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id)
);
create unique index if not exists uq_supply_rm_dispatch_no
  on public.supply_rm_dispatches(tenant_id, lower(dispatch_number));

create table if not exists public.supply_forging_receipts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  forging_order_id uuid not null references public.supply_forging_orders(id) on delete restrict,
  forging_supplier_id uuid not null references public.parties(id),
  receipt_number text not null,
  receipt_date date not null default current_date,
  received_qty_pcs numeric(18,3) not null check (received_qty_pcs > 0),
  rejected_qty_pcs numeric(18,3) not null default 0 check (rejected_qty_pcs >= 0),
  actual_rm_consumed_kg numeric(18,3) check (actual_rm_consumed_kg is null or actual_rm_consumed_kg >= 0),
  gross_weight_kg_snapshot numeric(18,6) not null check (gross_weight_kg_snapshot > 0),
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id)
);
create unique index if not exists uq_supply_forging_receipt_no
  on public.supply_forging_receipts(tenant_id, forging_order_id, lower(receipt_number));

create table if not exists public.supply_downstream_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  customer_order_id uuid not null references public.supply_customer_orders(id) on delete restrict,
  event_type text not null check (event_type in ('MACHINING','FINISHED_GOODS','CUSTOMER_DISPATCH')),
  reference_no text not null,
  event_date date not null default current_date,
  qty_pcs numeric(18,3) not null check (qty_pcs > 0),
  rejected_qty_pcs numeric(18,3) not null default 0 check (rejected_qty_pcs >= 0),
  invoice_no text, invoice_date date, asn_no text,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id), updated_by uuid references auth.users(id)
);
create unique index if not exists uq_supply_downstream_ref
  on public.supply_downstream_events(tenant_id, customer_order_id, event_type, lower(reference_no));

-- Quantity guards are DB-side poka-yoke controls and complement UI validation.
create or replace function public.qcms_supply_validate_rm_po()
returns trigger language plpgsql security definer set search_path=public as $$
declare allowed numeric; committed numeric;
begin
  select required_rm_kg*1.25 into allowed from public.supply_customer_orders where id=new.customer_order_id;
  if allowed is null then raise exception 'Customer order reference is invalid'; end if;
  select coalesce(sum(ordered_qty_kg),0) into committed from public.supply_rm_purchase_orders
   where customer_order_id=new.customer_order_id and status<>'CANCELLED' and id<>new.id;
  if committed+new.ordered_qty_kg > allowed + 0.0001 then
    raise exception 'Raw material order exceeds 125%% of customer-order requirement. Maximum permitted: % kg', round(allowed,3);
  end if;
  return new;
end; $$;
drop trigger if exists trg_supply_validate_rm_po on public.supply_rm_purchase_orders;
create trigger trg_supply_validate_rm_po before insert or update of customer_order_id,ordered_qty_kg,status
on public.supply_rm_purchase_orders for each row when (new.status<>'CANCELLED') execute function public.qcms_supply_validate_rm_po();

create or replace function public.qcms_supply_validate_rm_dispatch()
returns trigger language plpgsql security definer set search_path=public as $$
declare received numeric; dispatched numeric;
begin
  select coalesce(sum(received_qty_kg),0) into received from public.supply_rm_receipts where customer_order_id=new.customer_order_id;
  select coalesce(sum(qty_kg),0) into dispatched from public.supply_rm_dispatches where customer_order_id=new.customer_order_id and id<>new.id;
  if dispatched+new.qty_kg > received + 0.0001 then
    raise exception 'Raw material dispatch cannot exceed material received against this customer order. Available: % kg', round(received-dispatched,3);
  end if;
  return new;
end; $$;
drop trigger if exists trg_supply_validate_rm_dispatch on public.supply_rm_dispatches;
create trigger trg_supply_validate_rm_dispatch before insert or update of customer_order_id,qty_kg
on public.supply_rm_dispatches for each row execute function public.qcms_supply_validate_rm_dispatch();

-- Map tables into module permissions.
create or replace function public.qsms_module_for_table(target_table text)
returns text language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments','part_standard_links') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then 'NPD_APQP'
 when target_table='qc_calculation_records' then 'QC_CALCULATION_TOOLS'
 when target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then 'COMPLAINT_MANAGEMENT'
 when target_table in ('supply_customer_orders','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then 'SUPPLY_CHAIN'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links','processes','inspection_stages','master_value_catalog','customer_standards') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
 elsif target_table in ('employees','quality_assets') then return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
 elsif target_table='inward_lots' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('production_batches','batch_movements','osp_jobs') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA');
 elsif target_table in ('inspection_reports','inspection_results') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
 elsif target_table='lab_tests' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
 elsif target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION');
 elsif target_table='qc_calculation_records' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA');
 elsif target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('supply_customer_orders','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION');
 end if;
 return false;
end; $$;

-- Tenant RLS, audit and update timestamp triggers.
do $$
declare table_name text;
begin
 foreach table_name in array array['supply_customer_orders','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events'] loop
  execute format('alter table public.%I enable row level security', table_name);
  execute format('drop policy if exists tenant_select on public.%I', table_name);
  execute format('drop policy if exists tenant_insert on public.%I', table_name);
  execute format('drop policy if exists tenant_update on public.%I', table_name);
  execute format('drop policy if exists tenant_delete on public.%I', table_name);
  execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id=public.current_tenant_id())', table_name);
  execute format('create policy tenant_insert on public.%I for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
  execute format('create policy tenant_update on public.%I for update to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L)) with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name, table_name);
  execute format('create policy tenant_delete on public.%I for delete to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
  execute format('drop trigger if exists trg_touch_updated_at on public.%I', table_name);
  execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', table_name);
  execute format('drop trigger if exists trg_audit_row_change on public.%I', table_name);
  execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()', table_name);
 end loop;
end $$;
