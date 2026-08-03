-- QSMS 4.9.0 — OSP material-out, pre-receipt sample gate, OSP inward and release inspections.
begin;

-- -----------------------------------------------------------------------------
-- Part-wise process specification master
-- -----------------------------------------------------------------------------
create table if not exists public.part_process_specifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id) on delete cascade,
  process_id uuid not null references public.processes(id),
  inward_type text not null default 'OSP_PROCESS',
  process_specification text not null,
  dimensional_required boolean not null default true,
  metlab_required boolean not null default true,
  sample_quantity integer not null default 1 check (sample_quantity between 1 and 20),
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  constraint part_process_specifications_inward_type_check
    check (inward_type in ('MATERIAL_INWARD','OSP_PROCESS')),
  unique (tenant_id, part_id, process_id, inward_type)
);

alter table public.part_process_specifications enable row level security;
drop policy if exists tenant_select on public.part_process_specifications;
drop policy if exists tenant_insert on public.part_process_specifications;
drop policy if exists tenant_update on public.part_process_specifications;
drop policy if exists tenant_delete on public.part_process_specifications;
create policy tenant_select on public.part_process_specifications
  for select to authenticated using (tenant_id=public.current_tenant_id());
create policy tenant_insert on public.part_process_specifications
  for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.can_write_table('parts'));
create policy tenant_update on public.part_process_specifications
  for update to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table('parts'))
  with check (tenant_id=public.current_tenant_id() and public.can_write_table('parts'));
create policy tenant_delete on public.part_process_specifications
  for delete to authenticated using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

drop trigger if exists trg_part_process_specifications_touch on public.part_process_specifications;
create trigger trg_part_process_specifications_touch
before update on public.part_process_specifications
for each row execute function public.touch_updated_at();

grant select,insert,update,delete on public.part_process_specifications to authenticated;

-- -----------------------------------------------------------------------------
-- Inspection layouts identify the inward source they control.
-- -----------------------------------------------------------------------------
alter table public.inspection_plans
  add column if not exists inward_type text not null default 'MATERIAL_INWARD';
alter table public.inspection_plans drop constraint if exists inspection_plans_inward_type_check;
alter table public.inspection_plans add constraint inspection_plans_inward_type_check
  check (inward_type in ('MATERIAL_INWARD','OSP_PROCESS'));
create index if not exists idx_inspection_plans_osp_lookup
  on public.inspection_plans(part_id,process_id,inward_type,layout_type,status,effective_date desc);

-- -----------------------------------------------------------------------------
-- Extend OSP genealogy with two quality gates.
-- -----------------------------------------------------------------------------
alter table public.osp_jobs
  add column if not exists source_inward_lot_id uuid references public.inward_lots(id),
  add column if not exists process_specification_id uuid references public.part_process_specifications(id),
  add column if not exists inward_type text not null default 'OSP_PROCESS',
  add column if not exists sample_quantity numeric not null default 1,
  add column if not exists sample_received_date date,
  add column if not exists sample_reference text,
  add column if not exists sample_gate_status text not null default 'PENDING',
  add column if not exists full_receipt_authorized_at timestamptz,
  add column if not exists full_receipt_authorized_by uuid references public.profiles(id),
  add column if not exists receipt_number text,
  add column if not exists vendor_invoice_number text,
  add column if not exists vendor_invoice_date date,
  add column if not exists tc_number text,
  add column if not exists tc_date date,
  add column if not exists receipt_quality_disposition text not null default 'PENDING',
  add column if not exists production_released_at timestamptz,
  add column if not exists dispatch_remarks text;

alter table public.osp_jobs drop constraint if exists osp_jobs_inward_type_check;
alter table public.osp_jobs add constraint osp_jobs_inward_type_check
  check (inward_type='OSP_PROCESS');
alter table public.osp_jobs drop constraint if exists osp_jobs_sample_gate_status_check;
alter table public.osp_jobs add constraint osp_jobs_sample_gate_status_check
  check (sample_gate_status in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.osp_jobs drop constraint if exists osp_jobs_receipt_quality_disposition_check;
alter table public.osp_jobs add constraint osp_jobs_receipt_quality_disposition_check
  check (receipt_quality_disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.osp_jobs drop constraint if exists osp_jobs_sample_quantity_check;
alter table public.osp_jobs add constraint osp_jobs_sample_quantity_check
  check (sample_quantity>0 and sample_quantity<=quantity_dispatched);
create unique index if not exists uq_osp_receipt_number
  on public.osp_jobs(tenant_id,receipt_number) where receipt_number is not null;
create index if not exists idx_osp_source_inward
  on public.osp_jobs(source_inward_lot_id,status,dispatch_date desc);
create index if not exists idx_osp_quality_gates
  on public.osp_jobs(sample_gate_status,receipt_quality_disposition,receipt_status,status);

alter table public.inspection_reports
  add column if not exists inspection_scope text not null default 'MATERIAL_INWARD',
  add column if not exists process_specification_snapshot text,
  add column if not exists vendor_batch_number_snapshot text;
alter table public.inspection_reports drop constraint if exists inspection_reports_scope_check;
alter table public.inspection_reports add constraint inspection_reports_scope_check
  check (inspection_scope in ('MATERIAL_INWARD','OSP_SAMPLE','OSP_RECEIPT'));

alter table public.lab_tests
  add column if not exists inspection_scope text not null default 'MATERIAL_INWARD',
  add column if not exists process_specification_snapshot text,
  add column if not exists vendor_batch_number_snapshot text;
alter table public.lab_tests drop constraint if exists lab_tests_scope_check;
alter table public.lab_tests add constraint lab_tests_scope_check
  check (inspection_scope in ('MATERIAL_INWARD','OSP_SAMPLE','OSP_RECEIPT'));

create index if not exists idx_dimensional_osp_scope
  on public.inspection_reports(osp_job_id,inspection_scope,report_type,decision_at desc,updated_at desc);
create index if not exists idx_metlab_osp_scope
  on public.lab_tests(osp_job_id,inspection_scope,test_type,decision_at desc,updated_at desc);

-- Existing root production allocation used steel kg while OSP quantities are pieces.
-- Root batches now use the controlled Part Production Quantity when available.
create or replace function public.enforce_batch_genealogy()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  inward_row public.inward_lots%rowtype;
  parent_row public.production_batches%rowtype;
  allocated_quantity numeric;
  direct_children_quantity numeric;
  inward_piece_quantity numeric;
begin
  select * into inward_row from public.inward_lots where id=new.inward_lot_id;
  if inward_row.id is null then raise exception 'Production batch requires a valid Material Inward record'; end if;
  if inward_row.tenant_id<>new.tenant_id then raise exception 'Production batch tenant mismatch'; end if;
  if inward_row.status<>'RELEASED' or inward_row.quality_disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'Production or OSP allocation is allowed only after Material Inward quality release';
  end if;
  inward_piece_quantity:=coalesce(nullif(inward_row.accepted_production_quantity_pcs,0),nullif(inward_row.production_quantity_pcs,0),inward_row.quantity_accepted,0);
  if inward_piece_quantity<=0 then raise exception 'The Material Inward record has no released production quantity'; end if;

  if new.parent_batch_id is not null then
    select * into parent_row from public.production_batches where id=new.parent_batch_id;
    if parent_row.id is null or parent_row.tenant_id<>new.tenant_id then raise exception 'Invalid parent production batch'; end if;
    if parent_row.inward_lot_id<>new.inward_lot_id then raise exception 'Child batch must retain the source Material Inward genealogy'; end if;
    select coalesce(sum(quantity_started),0) into allocated_quantity
      from public.production_batches where parent_batch_id=parent_row.id and (new.id is null or id<>new.id);
    if allocated_quantity+new.quantity_started>parent_row.quantity_started then
      raise exception 'Child batch quantity exceeds the parent batch balance';
    end if;
  else
    select coalesce(sum(quantity_started),0) into allocated_quantity
      from public.production_batches where inward_lot_id=inward_row.id and parent_batch_id is null and (new.id is null or id<>new.id);
    if allocated_quantity+new.quantity_started>inward_piece_quantity then
      raise exception 'Production batch quantity exceeds the released Material Inward production balance';
    end if;
  end if;

  select coalesce(sum(quantity_started),0) into direct_children_quantity
    from public.production_batches where parent_batch_id=new.id;
  if direct_children_quantity>new.quantity_started then
    raise exception 'Batch quantity cannot be reduced below quantities allocated to child batches';
  end if;
  new.part_id:=inward_row.part_id;
  new.heat_number:=inward_row.heat_number;
  new.heat_code:=inward_row.heat_code;
  return new;
end;
$$;

-- OSP genealogy additionally requires the Part Master process specification.
create or replace function public.enforce_osp_genealogy()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  source_row public.production_batches%rowtype;
  child_row public.production_batches%rowtype;
  inward_row public.inward_lots%rowtype;
  vendor_row public.parties%rowtype;
  process_row public.processes%rowtype;
  specification_row public.part_process_specifications%rowtype;
begin
  select * into source_row from public.production_batches where id=new.source_batch_id;
  select * into child_row from public.production_batches where id=new.osp_batch_id;
  select * into inward_row from public.inward_lots where id=coalesce(new.source_inward_lot_id,source_row.inward_lot_id);
  select * into vendor_row from public.parties where id=new.vendor_id;
  select * into process_row from public.processes where id=new.process_id;
  select * into specification_row from public.part_process_specifications where id=new.process_specification_id;
  if source_row.id is null or child_row.id is null or inward_row.id is null then raise exception 'Source, OSP child batch and Material Inward genealogy are required'; end if;
  if source_row.tenant_id<>new.tenant_id or child_row.tenant_id<>new.tenant_id or inward_row.tenant_id<>new.tenant_id then raise exception 'OSP genealogy tenant mismatch'; end if;
  if source_row.inward_lot_id<>inward_row.id or child_row.inward_lot_id<>inward_row.id then raise exception 'OSP batches must retain the selected Material Inward genealogy'; end if;
  if child_row.parent_batch_id<>source_row.id then raise exception 'OSP batch must be a child of the dispatched source batch'; end if;
  if child_row.heat_number<>source_row.heat_number or child_row.heat_code<>source_row.heat_code then raise exception 'OSP child batch Heat genealogy mismatch'; end if;
  if child_row.quantity_started<>new.quantity_dispatched then raise exception 'OSP child batch quantity must equal the dispatched quantity'; end if;
  if vendor_row.id is null or vendor_row.tenant_id<>new.tenant_id or not('OSP_VENDOR'=any(vendor_row.party_types))
     or coalesce(vendor_row.approval_status,'')<>'APPROVED' or coalesce(vendor_row.status,'')<>'ACTIVE' then
    raise exception 'OSP dispatch requires an active approved OSP vendor';
  end if;
  if process_row.id is null or process_row.tenant_id<>new.tenant_id or process_row.process_type<>'OUTSOURCED' or coalesce(process_row.status,'')<>'ACTIVE' then
    raise exception 'OSP dispatch requires an active outsourced Process Master';
  end if;
  if specification_row.id is null or specification_row.tenant_id<>new.tenant_id or specification_row.part_id<>inward_row.part_id
     or specification_row.process_id<>new.process_id or specification_row.inward_type<>'OSP_PROCESS' or specification_row.status<>'ACTIVE' then
    raise exception 'Select an active OSP Process Specification from the Part Master for this Part and Process';
  end if;
  new.source_inward_lot_id:=inward_row.id;
  new.part_id:=inward_row.part_id;
  new.process_specification:=specification_row.process_specification;
  new.required_tests:=array_remove(array[
    case when specification_row.dimensional_required then 'DIMENSIONAL' end,
    case when specification_row.metlab_required then 'METLAB' end
  ],null);
  new.sample_quantity:=coalesce(nullif(new.sample_quantity,0),specification_row.sample_quantity,1);
  return new;
end;
$$;

drop trigger if exists trg_osp_genealogy on public.osp_jobs;
create trigger trg_osp_genealogy
before insert or update of source_batch_id,osp_batch_id,source_inward_lot_id,part_id,vendor_id,process_id,process_specification_id,quantity_dispatched,sample_quantity
on public.osp_jobs for each row execute function public.enforce_osp_genealogy();

-- -----------------------------------------------------------------------------
-- Document sequences and module permissions
-- -----------------------------------------------------------------------------
insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency)
select id,'OSP_JOB','OSP-'||coalesce(nullif(plant_code,''),'D9'),'YYYY',0,5,'YEARLY' from public.tenants
on conflict(tenant_id,sequence_code) do nothing;
insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency)
select id,'OSP_RECEIPT','OSP-IN-'||coalesce(nullif(plant_code,''),'D9'),'YYYY',0,5,'YEARLY' from public.tenants
on conflict(tenant_id,sequence_code) do nothing;

create or replace function public.qsms_module_for_table(target_table text) returns text language sql immutable as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','document_attachments') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','processes','inspection_stages','master_value_catalog') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
 elsif target_table in ('employees','quality_assets') then return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
 elsif target_table='inward_lots' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('production_batches','batch_movements','osp_jobs') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA');
 elsif target_table in ('inspection_reports','inspection_results') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
 elsif target_table='lab_tests' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
 end if;
 return false;
end;
$$;

create or replace function public.qsms_next_document_number(p_sequence_code text) returns text
language plpgsql security definer set search_path=public,auth as $$
declare v_tenant uuid:=public.current_tenant_id();v_row public.number_sequences%rowtype;v_year integer:=extract(year from current_date)::integer;v_year_text text;v_next bigint;v_target_table text;
begin
 if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required';end if;
 v_target_table:=case upper(p_sequence_code)
   when 'INWARD' then 'inward_lots'
   when 'DIMENSIONAL_REPORT' then 'inspection_reports'
   when 'METLAB_REPORT' then 'lab_tests'
   when 'OSP_JOB' then 'osp_jobs'
   when 'OSP_RECEIPT' then 'osp_jobs'
   else 'rmtc_approvals' end;
 if not public.can_write_table(v_target_table) then raise exception 'Your QSMS role cannot create this controlled document number';end if;
 select * into v_row from public.number_sequences where tenant_id=v_tenant and upper(sequence_code)=upper(p_sequence_code) for update;
 if v_row.id is null then raise exception 'Document number sequence % is not configured',p_sequence_code;end if;
 if coalesce(v_row.reset_frequency,'YEARLY')='YEARLY' and coalesce(v_row.last_reset_year,0)<>v_year then v_row.current_value:=0;v_row.last_reset_year:=v_year;end if;
 v_next:=v_row.current_value+1;
 update public.number_sequences set current_value=v_next,last_reset_year=v_row.last_reset_year,updated_at=now(),updated_by=auth.uid() where id=v_row.id;
 v_year_text:=case upper(coalesce(v_row.year_format,'YYYY')) when 'YY' then right(v_year::text,2) when 'NONE' then null else v_year::text end;
 return concat_ws('-',v_row.prefix,v_year_text,lpad(v_next::text,v_row.padding,'0'));
end;
$$;

-- -----------------------------------------------------------------------------
-- Controlled OSP transaction RPCs
-- -----------------------------------------------------------------------------
create or replace function public.qsms_create_osp_dispatch(
  p_inward_lot_id uuid,p_vendor_id uuid,p_process_id uuid,p_process_specification_id uuid,
  p_dispatch_date date,p_dispatch_challan text,p_quantity_dispatched numeric,
  p_expected_return_date date,p_sample_quantity numeric,p_remarks text
) returns jsonb
language plpgsql security definer set search_path=public,auth as $$
declare
  tid uuid:=public.current_tenant_id();
  inward_row public.inward_lots%rowtype;
  specification_row public.part_process_specifications%rowtype;
  source_row public.production_batches%rowtype;
  child_row public.production_batches%rowtype;
  job_row public.osp_jobs%rowtype;
  total_pcs numeric;allocated_pcs numeric;available_pcs numeric;
  job_number text;source_code text;child_code text;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QSMS session is required'; end if;
  if not public.can_write_table('osp_jobs') then raise exception 'OSP Transactions create permission is required'; end if;
  select * into inward_row from public.inward_lots where id=p_inward_lot_id and tenant_id=tid for update;
  if inward_row.id is null then raise exception 'Select a valid Material Inward record'; end if;
  if inward_row.status<>'RELEASED' or inward_row.quality_disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'OSP Material Out is allowed only after Material Inward Dimensional and MetLAB release';
  end if;
  select * into specification_row from public.part_process_specifications
    where id=p_process_specification_id and tenant_id=tid and part_id=inward_row.part_id
      and process_id=p_process_id and inward_type='OSP_PROCESS' and status='ACTIVE';
  if specification_row.id is null then raise exception 'The selected Part has no active OSP Process Specification for this Process'; end if;
  if nullif(btrim(coalesce(p_dispatch_challan,'')),'') is null then raise exception 'Material Out challan number is required'; end if;
  if coalesce(p_quantity_dispatched,0)<=0 then raise exception 'Material Out quantity must be greater than zero'; end if;
  total_pcs:=coalesce(nullif(inward_row.accepted_production_quantity_pcs,0),nullif(inward_row.production_quantity_pcs,0),0);
  if total_pcs<=0 then raise exception 'The Material Inward has no accepted production quantity'; end if;
  select coalesce(sum(o.quantity_dispatched),0) into allocated_pcs
    from public.osp_jobs o where o.tenant_id=tid and o.source_inward_lot_id=inward_row.id and o.status<>'CANCELLED';
  available_pcs:=greatest(total_pcs-allocated_pcs,0);
  if p_quantity_dispatched>available_pcs then raise exception 'OSP Material Out quantity % exceeds available quantity % pieces',p_quantity_dispatched,available_pcs; end if;

  source_code:='SRC-'||inward_row.inward_number;
  select * into source_row from public.production_batches where tenant_id=tid and batch_code=source_code for update;
  if source_row.id is null then
    insert into public.production_batches(tenant_id,batch_code,part_id,inward_lot_id,parent_batch_id,heat_number,heat_code,current_process_id,work_order,quantity_started,quantity_available,status,remarks)
    values(tid,source_code,inward_row.part_id,inward_row.id,null,inward_row.heat_number,inward_row.heat_code,null,'OSP SOURCE',total_pcs,total_pcs,'RELEASED','Automatically created from released Material Inward')
    returning * into source_row;
  end if;

  job_number:=public.qsms_next_document_number('OSP_JOB');
  child_code:=job_number||'-BATCH';
  insert into public.production_batches(tenant_id,batch_code,part_id,inward_lot_id,parent_batch_id,heat_number,heat_code,current_process_id,work_order,quantity_started,quantity_available,status,remarks)
  values(tid,child_code,inward_row.part_id,inward_row.id,source_row.id,inward_row.heat_number,inward_row.heat_code,p_process_id,job_number,p_quantity_dispatched,0,'AT_OSP','OSP vendor child batch')
  returning * into child_row;

  insert into public.osp_jobs(
    tenant_id,osp_job_number,source_batch_id,osp_batch_id,source_inward_lot_id,part_id,vendor_id,process_id,
    process_specification_id,dispatch_date,dispatch_challan,quantity_dispatched,expected_return_date,
    process_specification,required_tests,sample_quantity,status,dispatch_remarks
  ) values(
    tid,job_number,source_row.id,child_row.id,inward_row.id,inward_row.part_id,p_vendor_id,p_process_id,
    specification_row.id,p_dispatch_date,btrim(p_dispatch_challan),p_quantity_dispatched,p_expected_return_date,
    specification_row.process_specification,array_remove(array[
      case when specification_row.dimensional_required then 'DIMENSIONAL' end,
      case when specification_row.metlab_required then 'METLAB' end],null),
    coalesce(nullif(p_sample_quantity,0),specification_row.sample_quantity,1),'AT_VENDOR',nullif(btrim(coalesce(p_remarks,'')),'')
  ) returning * into job_row;

  update public.production_batches set quantity_available=greatest(total_pcs-(allocated_pcs+p_quantity_dispatched),0),updated_at=now(),updated_by=auth.uid()
    where id=source_row.id;
  insert into public.batch_movements(tenant_id,batch_id,movement_type,from_process_id,to_process_id,quantity,movement_date,reference,remarks)
    values(tid,source_row.id,'OSP_DISPATCH',source_row.current_process_id,p_process_id,p_quantity_dispatched,p_dispatch_date,job_number,btrim(p_dispatch_challan));
  return to_jsonb(job_row)||jsonb_build_object('available_after_dispatch',greatest(available_pcs-p_quantity_dispatched,0));
end;
$$;

create or replace function public.qsms_record_osp_sample(
  p_osp_job_id uuid,p_sample_received_date date,p_sample_reference text,p_vendor_batch_number text,p_sample_quantity numeric
) returns jsonb
language plpgsql security definer set search_path=public,auth as $$
declare tid uuid:=public.current_tenant_id();job_row public.osp_jobs%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QSMS session is required'; end if;
  if not public.can_write_table('osp_jobs') then raise exception 'OSP Transactions edit permission is required'; end if;
  select * into job_row from public.osp_jobs where id=p_osp_job_id and tenant_id=tid for update;
  if job_row.id is null then raise exception 'OSP Material Out record was not found'; end if;
  if job_row.quantity_received>0 then raise exception 'The full OSP batch is already inwarded'; end if;
  if job_row.status in ('REJECTED','CANCELLED') then raise exception 'Sample receipt is not allowed for a rejected or cancelled OSP job'; end if;
  if nullif(btrim(coalesce(p_sample_reference,'')),'') is null then raise exception 'Sample reference is required'; end if;
  if nullif(btrim(coalesce(p_vendor_batch_number,'')),'') is null then raise exception 'OSP Vendor Batch Number is required for the sample'; end if;
  if coalesce(p_sample_quantity,0)<=0 or p_sample_quantity>job_row.quantity_dispatched then raise exception 'Enter a valid sample quantity'; end if;
  update public.osp_jobs set sample_received_date=p_sample_received_date,sample_reference=btrim(p_sample_reference),
    vendor_batch_number=btrim(p_vendor_batch_number),sample_quantity=p_sample_quantity,sample_gate_status='PENDING',
    full_receipt_authorized_at=null,full_receipt_authorized_by=null,updated_at=now(),updated_by=auth.uid()
  where id=job_row.id returning * into job_row;
  return to_jsonb(job_row);
end;
$$;

create or replace function public.qsms_receive_osp_batch(
  p_osp_job_id uuid,p_receipt_date date,p_receipt_challan text,p_vendor_invoice_number text,p_vendor_invoice_date date,
  p_tc_number text,p_tc_date date,p_vendor_batch_number text,p_quantity_received numeric,p_remarks text
) returns jsonb
language plpgsql security definer set search_path=public,auth as $$
declare tid uuid:=public.current_tenant_id();job_row public.osp_jobs%rowtype;receipt_no text;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QSMS session is required'; end if;
  if not public.can_write_table('osp_jobs') then raise exception 'OSP Transactions create/edit permission is required'; end if;
  select * into job_row from public.osp_jobs where id=p_osp_job_id and tenant_id=tid for update;
  if job_row.id is null then raise exception 'OSP Material Out record was not found'; end if;
  if job_row.sample_gate_status not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'Full OSP inward is blocked until the one-part Sample Dimensional and MetLAB inspections are Accepted or Accepted Under Reserve';
  end if;
  if job_row.quantity_received>0 then raise exception 'The full OSP batch has already been inwarded'; end if;
  if coalesce(p_quantity_received,0)<>job_row.quantity_dispatched then
    raise exception 'Full OSP inward quantity must equal the dispatched quantity of % pieces',job_row.quantity_dispatched;
  end if;
  if nullif(btrim(coalesce(p_receipt_challan,'')),'') is null or nullif(btrim(coalesce(p_vendor_invoice_number,'')),'') is null
     or p_vendor_invoice_date is null or nullif(btrim(coalesce(p_tc_number,'')),'') is null or p_tc_date is null
     or nullif(btrim(coalesce(p_vendor_batch_number,'')),'') is null then
    raise exception 'Receipt challan, Vendor Invoice Number/Date, TC Number/Date and Vendor Batch Number are mandatory';
  end if;
  if job_row.vendor_batch_number is not null and upper(btrim(job_row.vendor_batch_number))<>upper(btrim(p_vendor_batch_number)) then
    raise exception 'Vendor Batch Number must match the batch validated during the sample inspection';
  end if;
  receipt_no:=public.qsms_next_document_number('OSP_RECEIPT');
  update public.osp_jobs set receipt_number=receipt_no,receipt_date=p_receipt_date,receipt_challan=btrim(p_receipt_challan),
    vendor_invoice_number=btrim(p_vendor_invoice_number),vendor_invoice_date=p_vendor_invoice_date,
    tc_number=btrim(p_tc_number),tc_date=p_tc_date,vendor_batch_number=btrim(p_vendor_batch_number),
    quantity_received=p_quantity_received,quantity_rejected_at_receipt=0,receipt_status='COMPLETE',
    receipt_quality_disposition='PENDING',inspection_status='PENDING',status='PART_RECEIVED',
    receipt_remarks=nullif(btrim(coalesce(p_remarks,'')),''),updated_at=now(),updated_by=auth.uid()
  where id=job_row.id returning * into job_row;
  update public.production_batches set vendor_batch_number=job_row.vendor_batch_number,quantity_available=0,
    status='HOLD_PENDING_OSP_INSPECTION',updated_at=now(),updated_by=auth.uid() where id=job_row.osp_batch_id;
  insert into public.batch_movements(tenant_id,batch_id,movement_type,from_process_id,to_process_id,quantity,movement_date,reference,remarks)
    values(tid,job_row.osp_batch_id,'OSP_RECEIPT',job_row.process_id,null,p_quantity_received,p_receipt_date,receipt_no,btrim(p_receipt_challan));
  return to_jsonb(job_row);
end;
$$;

-- -----------------------------------------------------------------------------
-- OSP inspection source guards
-- -----------------------------------------------------------------------------
create or replace function public.enforce_osp_dimensional_source()
returns trigger language plpgsql security definer set search_path=public,auth as $$
declare job_row public.osp_jobs%rowtype;plan_row public.inspection_plans%rowtype;vendor_id uuid;
begin
  if new.osp_job_id is null then
    new.inspection_scope:='MATERIAL_INWARD';
    return new;
  end if;
  select * into job_row from public.osp_jobs where id=new.osp_job_id;
  if job_row.id is null or job_row.tenant_id<>new.tenant_id then raise exception 'Invalid OSP job for Dimensional inspection'; end if;
  if new.inspection_scope not in ('OSP_SAMPLE','OSP_RECEIPT') then raise exception 'Select OSP Sample or OSP Receipt inspection scope'; end if;
  if new.inspection_scope='OSP_SAMPLE' and job_row.sample_received_date is null then raise exception 'Record the one-part OSP sample receipt before inspection'; end if;
  if new.inspection_scope='OSP_RECEIPT' and job_row.quantity_received<=0 then raise exception 'Full OSP inward is required before receipt inspection'; end if;
  select * into plan_row from public.inspection_plans where id=new.inspection_plan_id;
  if plan_row.id is null or plan_row.part_id<>job_row.part_id or plan_row.process_id<>job_row.process_id
     or plan_row.inward_type<>'OSP_PROCESS' or plan_row.layout_type<>'DIMENSIONAL' or plan_row.status<>'APPROVED' then
    raise exception 'Use an Approved OSP Dimensional layout matching the Part and Process';
  end if;
  new.inward_lot_id:=null;new.part_id:=job_row.part_id;new.process_id:=job_row.process_id;new.batch_id:=job_row.osp_batch_id;
  new.heat_number:=(select heat_number from public.production_batches where id=job_row.source_batch_id);
  new.heat_code:=(select heat_code from public.production_batches where id=job_row.source_batch_id);
  new.supplier_id:=job_row.vendor_id;new.process_specification_snapshot:=job_row.process_specification;
  new.vendor_batch_number_snapshot:=job_row.vendor_batch_number;
  new.production_quantity_pcs:=case when new.inspection_scope='OSP_SAMPLE' then job_row.sample_quantity else job_row.quantity_received end;
  new.lot_quantity:=new.production_quantity_pcs;
  return new;
end;
$$;

drop trigger if exists trg_osp_dimensional_source on public.inspection_reports;
create trigger trg_osp_dimensional_source
before insert or update of osp_job_id,inspection_scope,inspection_plan_id,part_id,process_id,batch_id,inward_lot_id
on public.inspection_reports for each row execute function public.enforce_osp_dimensional_source();

create or replace function public.enforce_osp_metlab_source()
returns trigger language plpgsql security definer set search_path=public,auth as $$
declare job_row public.osp_jobs%rowtype;plan_row public.inspection_plans%rowtype;
begin
  if new.osp_job_id is null then
    new.inspection_scope:='MATERIAL_INWARD';
    return new;
  end if;
  select * into job_row from public.osp_jobs where id=new.osp_job_id;
  if job_row.id is null or job_row.tenant_id<>new.tenant_id then raise exception 'Invalid OSP job for MetLAB inspection'; end if;
  if new.inspection_scope not in ('OSP_SAMPLE','OSP_RECEIPT') then raise exception 'Select OSP Sample or OSP Receipt inspection scope'; end if;
  if new.inspection_scope='OSP_SAMPLE' and job_row.sample_received_date is null then raise exception 'Record the one-part OSP sample receipt before inspection'; end if;
  if new.inspection_scope='OSP_RECEIPT' and job_row.quantity_received<=0 then raise exception 'Full OSP inward is required before receipt inspection'; end if;
  select * into plan_row from public.inspection_plans where id=new.layout_plan_id;
  if plan_row.id is null or plan_row.part_id<>job_row.part_id or plan_row.process_id<>job_row.process_id
     or plan_row.inward_type<>'OSP_PROCESS' or plan_row.layout_type<>'METLAB' or plan_row.status<>'APPROVED' then
    raise exception 'Use an Approved OSP MetLAB layout matching the Part and Process';
  end if;
  new.inward_lot_id:=null;new.part_id:=job_row.part_id;new.process_id:=job_row.process_id;new.batch_id:=job_row.osp_batch_id;
  new.heat_number:=(select heat_number from public.production_batches where id=job_row.source_batch_id);
  new.heat_code:=(select heat_code from public.production_batches where id=job_row.source_batch_id);
  new.supplier_id:=job_row.vendor_id;new.process_specification_snapshot:=job_row.process_specification;
  new.vendor_batch_number_snapshot:=job_row.vendor_batch_number;
  new.production_quantity_pcs:=case when new.inspection_scope='OSP_SAMPLE' then job_row.sample_quantity else job_row.quantity_received end;
  return new;
end;
$$;

drop trigger if exists trg_osp_metlab_source on public.lab_tests;
create trigger trg_osp_metlab_source
before insert or update of osp_job_id,inspection_scope,layout_plan_id,part_id,process_id,batch_id,inward_lot_id
on public.lab_tests for each row execute function public.enforce_osp_metlab_source();

-- -----------------------------------------------------------------------------
-- Two-stage OSP quality gate refresh
-- -----------------------------------------------------------------------------
create or replace function public.qsms_refresh_osp_quality_gate(p_osp_job_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare
  job_row public.osp_jobs%rowtype;
  sample_dim text:='PENDING';sample_met text:='PENDING';receipt_dim text:='PENDING';receipt_met text:='PENDING';
  sample_gate text:='PENDING';receipt_gate text:='PENDING';new_status text;new_inspection text:='PENDING';
begin
  select * into job_row from public.osp_jobs where id=p_osp_job_id for update;
  if job_row.id is null then raise exception 'OSP job was not found'; end if;
  select disposition into sample_dim from public.inspection_reports where osp_job_id=p_osp_job_id and report_type='DIMENSIONAL' and inspection_scope='OSP_SAMPLE'
    order by decision_at desc nulls last,updated_at desc limit 1;
  select disposition into sample_met from public.lab_tests where osp_job_id=p_osp_job_id and test_type='METLAB' and inspection_scope='OSP_SAMPLE'
    order by decision_at desc nulls last,updated_at desc limit 1;
  select disposition into receipt_dim from public.inspection_reports where osp_job_id=p_osp_job_id and report_type='DIMENSIONAL' and inspection_scope='OSP_RECEIPT'
    order by decision_at desc nulls last,updated_at desc limit 1;
  select disposition into receipt_met from public.lab_tests where osp_job_id=p_osp_job_id and test_type='METLAB' and inspection_scope='OSP_RECEIPT'
    order by decision_at desc nulls last,updated_at desc limit 1;
  sample_dim:=case when not('DIMENSIONAL'=any(job_row.required_tests)) then 'ACCEPTED' else coalesce(sample_dim,'PENDING') end;
  sample_met:=case when not('METLAB'=any(job_row.required_tests)) then 'ACCEPTED' else coalesce(sample_met,'PENDING') end;
  receipt_dim:=case when not('DIMENSIONAL'=any(job_row.required_tests)) then 'ACCEPTED' else coalesce(receipt_dim,'PENDING') end;
  receipt_met:=case when not('METLAB'=any(job_row.required_tests)) then 'ACCEPTED' else coalesce(receipt_met,'PENDING') end;

  if sample_dim='REJECTED' or sample_met='REJECTED' then sample_gate:='REJECTED';
  elsif sample_dim in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') and sample_met in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    sample_gate:=case when sample_dim='ACCEPTED_UNDER_RESERVE' or sample_met='ACCEPTED_UNDER_RESERVE' then 'ACCEPTED_UNDER_RESERVE' else 'ACCEPTED' end;
  elsif sample_dim='ON_HOLD' or sample_met='ON_HOLD' then sample_gate:='ON_HOLD'; end if;

  if receipt_dim='REJECTED' or receipt_met='REJECTED' then receipt_gate:='REJECTED';
  elsif receipt_dim in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') and receipt_met in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    receipt_gate:=case when receipt_dim='ACCEPTED_UNDER_RESERVE' or receipt_met='ACCEPTED_UNDER_RESERVE' then 'ACCEPTED_UNDER_RESERVE' else 'ACCEPTED' end;
  elsif receipt_dim='ON_HOLD' or receipt_met='ON_HOLD' then receipt_gate:='ON_HOLD'; end if;

  if job_row.quantity_received<=0 then
    new_status:=case when sample_gate='REJECTED' then 'REJECTED' else 'AT_VENDOR' end;
  elsif receipt_gate='REJECTED' then new_status:='REJECTED';
  elsif receipt_gate in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then new_status:='COMPLETED';
  else new_status:='PART_RECEIVED'; end if;
  new_inspection:=case receipt_gate when 'ACCEPTED' then 'PASS' when 'ACCEPTED_UNDER_RESERVE' then 'HOLD'
    when 'ON_HOLD' then 'HOLD' when 'REJECTED' then 'FAIL' else 'PENDING' end;

  update public.osp_jobs set sample_gate_status=sample_gate,
    full_receipt_authorized_at=case when sample_gate in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then coalesce(full_receipt_authorized_at,now()) else null end,
    full_receipt_authorized_by=case when sample_gate in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then coalesce(full_receipt_authorized_by,auth.uid()) else null end,
    receipt_quality_disposition=receipt_gate,inspection_status=new_inspection,status=new_status,
    production_released_at=case when new_status='COMPLETED' then coalesce(production_released_at,now()) else null end,
    updated_at=now(),updated_by=auth.uid() where id=job_row.id;
  update public.production_batches set
    status=case when new_status='COMPLETED' then 'RELEASED' when new_status='REJECTED' then 'REJECTED'
      when job_row.quantity_received>0 then 'HOLD_PENDING_OSP_INSPECTION' else 'AT_OSP' end,
    quantity_available=case when new_status='COMPLETED' then greatest(job_row.quantity_received-job_row.quantity_rejected_at_receipt,0) else 0 end,
    updated_at=now(),updated_by=auth.uid() where id=job_row.osp_batch_id;
  return jsonb_build_object('osp_job_id',p_osp_job_id,'sample_dimensional',sample_dim,'sample_metlab',sample_met,
    'sample_gate_status',sample_gate,'receipt_dimensional',receipt_dim,'receipt_metlab',receipt_met,
    'receipt_quality_disposition',receipt_gate,'status',new_status,'inspection_status',new_inspection);
end;
$$;

-- Replace the legacy one-stage OSP quality release trigger with a direct guard.
drop trigger if exists trg_osp_quality_release on public.osp_jobs;
create or replace function public.enforce_osp_receipt_gate()
returns trigger language plpgsql security definer set search_path=public,auth as $$
begin
  if new.quantity_received>0 then
    if new.sample_gate_status not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
      raise exception 'Full OSP inward requires Accepted or Accepted Under Reserve one-part sample inspections';
    end if;
    if new.quantity_received<>new.quantity_dispatched then raise exception 'OSP inward must receive the full dispatched batch quantity'; end if;
    if nullif(btrim(coalesce(new.vendor_invoice_number,'')),'') is null or new.vendor_invoice_date is null
       or nullif(btrim(coalesce(new.tc_number,'')),'') is null or new.tc_date is null
       or nullif(btrim(coalesce(new.vendor_batch_number,'')),'') is null then
      raise exception 'Vendor Invoice, TC and Vendor Batch details are mandatory for OSP inward';
    end if;
  end if;
  if new.status='COMPLETED' and new.receipt_quality_disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'OSP batch cannot be released to Production before post-receipt Dimensional and MetLAB acceptance';
  end if;
  return new;
end;
$$;
drop trigger if exists trg_osp_receipt_gate on public.osp_jobs;
create trigger trg_osp_receipt_gate
before insert or update of quantity_received,status,sample_gate_status,receipt_quality_disposition,vendor_invoice_number,vendor_invoice_date,tc_number,tc_date,vendor_batch_number
on public.osp_jobs for each row execute function public.enforce_osp_receipt_gate();

-- Finalization functions route Material Inward reports to the inward gate and OSP reports to the correct OSP gate.
create or replace function public.qsms_finalize_dimensional_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_report public.inspection_reports%rowtype;v_bad integer;v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_'));
begin
  if not public.qsms_has_module_approve('DIMENSIONAL_REPORT') then raise exception 'Dimensional Report approval permission is required'; end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.inspection_reports where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'Dimensional report was not found'; end if;
  select count(*) into v_bad from public.inspection_results where inspection_report_id=p_report_id and result not in ('PASS','NOT_APPLICABLE');
  if v_disposition='ACCEPTED' and v_bad>0 then raise exception 'Accepted is allowed only when every applicable characteristic passes'; end if;
  update public.inspection_reports set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=p_approved_by_employee_id,validated_at=now(),decision_at=case when v_disposition='ON_HOLD' then null else now() end,
    status=case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid() where id=p_report_id;
  if v_report.osp_job_id is not null then return public.qsms_refresh_osp_quality_gate(v_report.osp_job_id); end if;
  return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end;
$$;

create or replace function public.qsms_finalize_metlab_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_report public.lab_tests%rowtype;v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_'));v_bad integer:=0;
begin
  if not public.qsms_has_module_approve('METLAB_REPORT') then raise exception 'MetLAB Report approval permission is required'; end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.lab_tests where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'MetLAB report was not found'; end if;
  select count(*) into v_bad from (
    select coalesce(item->>'result','NOT_EVALUATED') result from jsonb_array_elements(coalesce(v_report.results->'rows','[]'::jsonb)) item
    union all select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'chemistry_rows','[]'::jsonb)) item
    union all select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'jominy_rows','[]'::jsonb)) item
    union all select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'requirement_rows','[]'::jsonb)) item
  ) evaluated where result not in ('PASS','NOT_APPLICABLE');
  if v_disposition='ACCEPTED' and v_bad>0 and btrim(coalesce(p_reason,''))='' then raise exception 'Manual acceptance reason is mandatory when applicable MetLAB results do not all pass'; end if;
  update public.lab_tests set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=p_approved_by_employee_id,validated_at=now(),decision_at=case when v_disposition='ON_HOLD' then null else now() end,
    status=case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid() where id=p_report_id;
  if v_report.osp_job_id is not null then return public.qsms_refresh_osp_quality_gate(v_report.osp_job_id); end if;
  return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end;
$$;

-- -----------------------------------------------------------------------------
-- Live OSP registers
-- -----------------------------------------------------------------------------
create or replace view public.v_qsms_osp_register
with (security_invoker=true)
as
select
  o.*,
  source_batch.heat_number,source_batch.heat_code,source_batch.batch_code as source_batch_code,
  osp_batch.batch_code as osp_batch_code,osp_batch.quantity_available as production_available_quantity,
  i.inward_number,i.inward_date,i.quality_disposition as source_quality_disposition,
  p.part_number,p.part_name,
  vendor.party_code as vendor_code,vendor.party_name as vendor_name,
  process.process_code,process.process_name,process.process_type,
  specification.inward_type as specification_inward_type,
  specification.dimensional_required,specification.metlab_required,
  coalesce((select r.disposition from public.inspection_reports r where r.osp_job_id=o.id and r.report_type='DIMENSIONAL' and r.inspection_scope='OSP_SAMPLE' order by r.decision_at desc nulls last,r.updated_at desc limit 1),'PENDING') as sample_dimensional_disposition,
  coalesce((select l.disposition from public.lab_tests l where l.osp_job_id=o.id and l.test_type='METLAB' and l.inspection_scope='OSP_SAMPLE' order by l.decision_at desc nulls last,l.updated_at desc limit 1),'PENDING') as sample_metlab_disposition,
  coalesce((select r.disposition from public.inspection_reports r where r.osp_job_id=o.id and r.report_type='DIMENSIONAL' and r.inspection_scope='OSP_RECEIPT' order by r.decision_at desc nulls last,r.updated_at desc limit 1),'PENDING') as receipt_dimensional_disposition,
  coalesce((select l.disposition from public.lab_tests l where l.osp_job_id=o.id and l.test_type='METLAB' and l.inspection_scope='OSP_RECEIPT' order by l.decision_at desc nulls last,l.updated_at desc limit 1),'PENDING') as receipt_metlab_disposition,
  (o.sample_gate_status in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')) as full_receipt_allowed,
  greatest(o.quantity_dispatched-o.quantity_received,0) as quantity_outstanding
from public.osp_jobs o
join public.production_batches source_batch on source_batch.id=o.source_batch_id
join public.production_batches osp_batch on osp_batch.id=o.osp_batch_id
join public.inward_lots i on i.id=o.source_inward_lot_id
join public.parts p on p.id=o.part_id
join public.parties vendor on vendor.id=o.vendor_id
join public.processes process on process.id=o.process_id
left join public.part_process_specifications specification on specification.id=o.process_specification_id;

create or replace view public.v_qsms_osp_dispatch_candidates
with (security_invoker=true)
as
select
  i.id as inward_lot_id,i.inward_number,i.inward_date,i.part_id,p.part_number,p.part_name,
  i.heat_number,i.heat_code,i.quality_disposition,i.status,
  coalesce(nullif(i.accepted_production_quantity_pcs,0),nullif(i.production_quantity_pcs,0),0) as released_production_quantity_pcs,
  coalesce((select sum(o.quantity_dispatched) from public.osp_jobs o where o.source_inward_lot_id=i.id and o.status<>'CANCELLED'),0) as osp_dispatched_quantity_pcs,
  greatest(coalesce(nullif(i.accepted_production_quantity_pcs,0),nullif(i.production_quantity_pcs,0),0)-
    coalesce((select sum(o.quantity_dispatched) from public.osp_jobs o where o.source_inward_lot_id=i.id and o.status<>'CANCELLED'),0),0) as osp_available_quantity_pcs
from public.inward_lots i join public.parts p on p.id=i.part_id
where i.status='RELEASED' and i.quality_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE');

grant select on public.v_qsms_osp_register,public.v_qsms_osp_dispatch_candidates to authenticated;

-- Password-protected Part Master process-specification deletion support.
create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid) returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare tid uuid:=public.current_tenant_id();role_name text:=coalesce(public.current_app_role(),'VIEWER');module_name text:=public.qsms_module_for_table(p_table_name);allowed boolean:=false;deleted_count integer:=0;
allowed_tables constant text[]:=array['parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages','quality_assets','inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments','rmtc_approvals','inward_lots','inspection_reports','inspection_results','lab_tests'];
begin
 if auth.uid() is null then raise exception 'Authentication required';end if;
 if p_table_name is null or not(p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table';end if;
 allowed:=role_name='ADMIN' or exists(select 1 from public.user_module_permissions p where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_archive);
 if not allowed then raise exception 'Delete permission is not assigned for this module';end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant';end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then raise exception 'This record is linked to another master or transaction. Deactivate it instead of deleting it.';
end;
$$;

revoke all on function public.qsms_create_osp_dispatch(uuid,uuid,uuid,uuid,date,text,numeric,date,numeric,text) from public,anon;
revoke all on function public.qsms_record_osp_sample(uuid,date,text,text,numeric) from public,anon;
revoke all on function public.qsms_receive_osp_batch(uuid,date,text,text,date,text,date,text,numeric,text) from public,anon;
revoke all on function public.qsms_refresh_osp_quality_gate(uuid) from public,anon;
grant execute on function public.qsms_create_osp_dispatch(uuid,uuid,uuid,uuid,date,text,numeric,date,numeric,text) to authenticated;
grant execute on function public.qsms_record_osp_sample(uuid,date,text,text,numeric) to authenticated;
grant execute on function public.qsms_receive_osp_batch(uuid,date,text,text,date,text,date,text,numeric,text) to authenticated;
grant execute on function public.qsms_refresh_osp_quality_gate(uuid) to authenticated;
grant execute on function public.qsms_finalize_dimensional_report(uuid,text,text,uuid,uuid) to authenticated;
grant execute on function public.qsms_finalize_metlab_report(uuid,text,text,uuid,uuid) to authenticated;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
