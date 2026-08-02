-- QSMS 4.8.1 — Heat-wise production allocation and MetLAB microstructure images.
-- Existing records are preserved. New production allocations are controlled in pieces and kilograms.
begin;

alter table public.rmtc_part_approvals
  add column if not exists planned_production_quantity_pcs numeric not null default 0,
  add column if not exists input_weight_kg numeric,
  add column if not exists planned_steel_quantity_kg numeric not null default 0;

alter table public.inward_lots
  add column if not exists accepted_production_quantity_pcs numeric not null default 0,
  add column if not exists rejected_production_quantity_pcs numeric not null default 0,
  add column if not exists hold_production_quantity_pcs numeric not null default 0,
  add column if not exists accepted_steel_quantity_kg numeric not null default 0,
  add column if not exists rejected_steel_quantity_kg numeric not null default 0,
  add column if not exists hold_steel_quantity_kg numeric not null default 0;

alter table public.lab_tests
  add column if not exists microstructure_image_1_path text,
  add column if not exists microstructure_image_2_path text,
  add column if not exists microstructure_image_3_path text,
  add column if not exists microstructure_image_4_path text,
  add column if not exists microstructure_caption_1 text,
  add column if not exists microstructure_caption_2 text,
  add column if not exists microstructure_caption_3 text,
  add column if not exists microstructure_caption_4 text;

alter table public.rmtc_part_approvals drop constraint if exists rmtc_part_planned_production_nonnegative;
alter table public.rmtc_part_approvals add constraint rmtc_part_planned_production_nonnegative
  check (planned_production_quantity_pcs >= 0 and planned_steel_quantity_kg >= 0 and (input_weight_kg is null or input_weight_kg >= 0));

alter table public.inward_lots drop constraint if exists inward_production_breakdown_nonnegative;
alter table public.inward_lots add constraint inward_production_breakdown_nonnegative
  check (
    accepted_production_quantity_pcs >= 0 and rejected_production_quantity_pcs >= 0 and hold_production_quantity_pcs >= 0
    and accepted_steel_quantity_kg >= 0 and rejected_steel_quantity_kg >= 0 and hold_steel_quantity_kg >= 0
  );

create index if not exists idx_rmtc_part_production_plan
  on public.rmtc_part_approvals(rmtc_approval_id,part_id,planned_production_quantity_pcs);
create index if not exists idx_inward_heat_production
  on public.inward_lots(rmtc_approval_id,rmtc_part_approval_id,heat_number);

-- Seed source weight and preserve any already-used production quantity as the minimum plan.
update public.rmtc_part_approvals pa
set input_weight_kg = coalesce(
      pa.input_weight_kg,
      (
        select coalesce(d.input_weight_kg,d.gross_weight_kg,d.forging_weight_kg)
        from public.rmtc_approvals r
        join public.part_raw_material_details d
          on d.tenant_id=pa.tenant_id and d.part_id=pa.part_id
         and d.supplier_id=r.supplier_id and d.status='ACTIVE'
        where r.id=pa.rmtc_approval_id
        order by case when d.id=r.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at
        limit 1
      )
    ),
    planned_production_quantity_pcs = greatest(
      coalesce(pa.planned_production_quantity_pcs,0),
      coalesce((select sum(coalesce(i.production_quantity_pcs,0)) from public.inward_lots i where i.rmtc_part_approval_id=pa.id),0)
    );

update public.rmtc_part_approvals
set planned_steel_quantity_kg=round(coalesce(planned_production_quantity_pcs,0)*coalesce(input_weight_kg,0),3);

-- Preserve existing inward records while classifying their previous total production quantity.
update public.inward_lots
set accepted_production_quantity_pcs = case
      when coalesce(accepted_production_quantity_pcs,0)+coalesce(rejected_production_quantity_pcs,0)+coalesce(hold_production_quantity_pcs,0)>0 then accepted_production_quantity_pcs
      when receipt_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then coalesce(production_quantity_pcs,0)
      else 0 end,
    rejected_production_quantity_pcs = case
      when coalesce(accepted_production_quantity_pcs,0)+coalesce(rejected_production_quantity_pcs,0)+coalesce(hold_production_quantity_pcs,0)>0 then rejected_production_quantity_pcs
      when receipt_disposition='REJECTED' then coalesce(production_quantity_pcs,0)
      else 0 end,
    hold_production_quantity_pcs = case
      when coalesce(accepted_production_quantity_pcs,0)+coalesce(rejected_production_quantity_pcs,0)+coalesce(hold_production_quantity_pcs,0)>0 then hold_production_quantity_pcs
      when receipt_disposition in ('PENDING','ON_HOLD') then coalesce(production_quantity_pcs,0)
      else 0 end;

update public.inward_lots
set accepted_steel_quantity_kg=round(coalesce(accepted_production_quantity_pcs,0)*coalesce(input_weight_kg,0),3),
    rejected_steel_quantity_kg=round(coalesce(rejected_production_quantity_pcs,0)*coalesce(input_weight_kg,0),3),
    hold_steel_quantity_kg=round(coalesce(hold_production_quantity_pcs,0)*coalesce(input_weight_kg,0),3);

create or replace function public.enforce_rmtc_part_production_plan()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  header_row public.rmtc_approvals%rowtype;
  source_row public.part_raw_material_details%rowtype;
  other_planned_steel numeric:=0;
  inward_pieces numeric:=0;
  planned_pieces numeric:=coalesce(new.planned_production_quantity_pcs,0);
  input_weight numeric;
begin
  select * into header_row from public.rmtc_approvals where id=new.rmtc_approval_id;
  if header_row.id is null then raise exception 'Linked RMTC header does not exist'; end if;

  select * into source_row from public.part_raw_material_details d
  where d.tenant_id=new.tenant_id and d.part_id=new.part_id and d.supplier_id=header_row.supplier_id and d.status='ACTIVE'
  order by case when d.id=header_row.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at
  limit 1;

  input_weight:=coalesce(new.input_weight_kg,source_row.input_weight_kg,source_row.gross_weight_kg,source_row.forging_weight_kg,0);
  if planned_pieces>0 and input_weight<=0 then
    raise exception 'Input Weight (kg/part) is required in Part Master supplier forging parameters';
  end if;
  new.input_weight_kg:=nullif(input_weight,0);
  new.planned_production_quantity_pcs:=planned_pieces;
  new.planned_steel_quantity_kg:=round(planned_pieces*input_weight,3);

  select coalesce(sum(coalesce(planned_steel_quantity_kg,0)),0) into other_planned_steel
  from public.rmtc_part_approvals
  where rmtc_approval_id=new.rmtc_approval_id and id<>new.id;
  if other_planned_steel+new.planned_steel_quantity_kg>header_row.certificate_quantity then
    raise exception 'Total planned production steel % kg exceeds RMTC steel quantity % kg',
      round(other_planned_steel+new.planned_steel_quantity_kg,3),header_row.certificate_quantity;
  end if;

  select coalesce(sum(coalesce(production_quantity_pcs,0)),0) into inward_pieces
  from public.inward_lots where rmtc_part_approval_id=new.id;
  if planned_pieces<inward_pieces then
    raise exception 'Planned production quantity cannot be reduced below % pieces already inwarded',inward_pieces;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_rmtc_part_production_plan on public.rmtc_part_approvals;
create trigger trg_rmtc_part_production_plan
before insert or update of rmtc_approval_id,part_id,planned_production_quantity_pcs,input_weight_kg
on public.rmtc_part_approvals
for each row execute function public.enforce_rmtc_part_production_plan();

create or replace function public.enforce_rmtc_certificate_production_limit()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare total_planned numeric;
begin
  select coalesce(sum(coalesce(planned_steel_quantity_kg,0)),0) into total_planned
  from public.rmtc_part_approvals where rmtc_approval_id=new.id;
  if total_planned>new.certificate_quantity then
    raise exception 'RMTC steel quantity cannot be reduced below planned production steel % kg',total_planned;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_rmtc_certificate_production_limit on public.rmtc_approvals;
create trigger trg_rmtc_certificate_production_limit
before update of certificate_quantity on public.rmtc_approvals
for each row execute function public.enforce_rmtc_certificate_production_limit();

create or replace function public.qsms_submit_rmtc(p_rmtc_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
  v_summary jsonb;
  v_pending integer;
  v_missing_plan integer;
  v_planned_steel numeric;
begin
  select * into v_header from public.rmtc_approvals
   where id=p_rmtc_id and tenant_id=public.current_tenant_id() for update;
  if v_header.id is null then raise exception 'RMTC record was not found'; end if;
  if v_header.status<>'DRAFT' then raise exception 'Only a Draft RMTC can be submitted'; end if;
  if not public.qsms_employee_has_authority(v_header.prepared_by_employee_id,'RMTC_PREPARE') then raise exception 'Select an active employee with RMTC preparation authority'; end if;
  if not public.qsms_employee_has_authority(v_header.validated_by_employee_id,'RMTC_VALIDATE') then raise exception 'Select an active employee with RMTC validation authority'; end if;
  if not public.qsms_employee_has_authority(v_header.approved_by_employee_id,'RMTC_APPROVE') then raise exception 'Select an active employee with RMTC approval authority'; end if;
  if not exists(select 1 from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id) then raise exception 'Select at least one Part Number for RMTC evaluation'; end if;
  select count(*) into v_pending from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id and worksheet_completed_at is null;
  if v_pending>0 then raise exception '% Part Worksheet(s) are not saved. Complete every covered Part Number before submission',v_pending; end if;
  select count(*),coalesce(sum(planned_steel_quantity_kg),0) into v_missing_plan,v_planned_steel
  from public.rmtc_part_approvals
  where rmtc_approval_id=p_rmtc_id and planned_production_quantity_pcs<=0;
  if v_missing_plan>0 then raise exception 'Part Production Quantity is mandatory for every covered Part Number'; end if;
  select coalesce(sum(planned_steel_quantity_kg),0) into v_planned_steel
  from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id;
  if v_planned_steel>v_header.certificate_quantity then
    raise exception 'Total planned production steel % kg exceeds RMTC steel quantity % kg',v_planned_steel,v_header.certificate_quantity;
  end if;
  if v_header.certificate_quantity<=0 then raise exception 'Certificate quantity must be greater than zero'; end if;
  v_summary:=public.qsms_evaluate_rmtc(p_rmtc_id);
  update public.rmtc_approvals set status='APPROVAL_PENDING',prepared_at=coalesce(prepared_at,now()),updated_at=now(),updated_by=auth.uid() where id=p_rmtc_id;
  return v_summary||jsonb_build_object('status','APPROVAL_PENDING','planned_steel_quantity_kg',v_planned_steel);
end;
$$;

create or replace function public.enforce_inward_rmtc_link()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  cert public.rmtc_approvals%rowtype;
  part_decision public.rmtc_part_approvals%rowtype;
  source_detail public.part_raw_material_details%rowtype;
  heat_allocated_steel numeric:=0;
  part_allocated_pieces numeric:=0;
  batch_allocated_pieces numeric:=0;
  accepted_pieces numeric:=coalesce(new.accepted_production_quantity_pcs,0);
  rejected_pieces numeric:=coalesce(new.rejected_production_quantity_pcs,0);
  hold_pieces numeric:=coalesce(new.hold_production_quantity_pcs,0);
  production_pieces numeric;
  input_weight numeric;
  required_steel numeric;
begin
  select * into cert from public.rmtc_approvals where id=new.rmtc_approval_id;
  if cert.id is null then raise exception 'Linked RMTC approval does not exist'; end if;
  if cert.tenant_id<>new.tenant_id then raise exception 'RMTC and inward tenant mismatch'; end if;
  if cert.status not in ('APPROVED','PARTIALLY_APPROVED') or cert.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'Material inward is allowed only against an Accepted or Accepted Under Reserve RMTC';
  end if;

  if new.rmtc_part_approval_id is null then
    select * into part_decision from public.rmtc_part_approvals
    where rmtc_approval_id=cert.id and part_id=coalesce(new.part_id,cert.part_id) limit 1;
  else
    select * into part_decision from public.rmtc_part_approvals
    where id=new.rmtc_part_approval_id and rmtc_approval_id=cert.id;
  end if;
  if part_decision.id is null then raise exception 'Select a covered RMTC Part Number'; end if;
  if part_decision.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'The selected RMTC Part Number is not accepted for inward';
  end if;

  if new.supplier_source_detail_id is not null then
    select * into source_detail from public.part_raw_material_details
    where id=new.supplier_source_detail_id and tenant_id=new.tenant_id and part_id=part_decision.part_id
      and supplier_id=cert.supplier_id and status='ACTIVE';
  end if;
  if source_detail.id is null then
    select * into source_detail from public.part_raw_material_details
    where tenant_id=new.tenant_id and part_id=part_decision.part_id and supplier_id=cert.supplier_id and status='ACTIVE'
    order by case when id=cert.selected_source_detail_id then 0 else 1 end,sequence_no,created_at limit 1;
  end if;
  if source_detail.id is null then raise exception 'Active supplier forging parameters are required in Part Master'; end if;

  if accepted_pieces+rejected_pieces+hold_pieces<=0 and coalesce(new.production_quantity_pcs,0)>0 then
    if new.receipt_disposition='REJECTED' then rejected_pieces:=new.production_quantity_pcs;
    elsif new.receipt_disposition in ('PENDING','ON_HOLD') then hold_pieces:=new.production_quantity_pcs;
    else accepted_pieces:=new.production_quantity_pcs;
    end if;
  end if;
  production_pieces:=accepted_pieces+rejected_pieces+hold_pieces;
  input_weight:=coalesce(new.input_weight_kg,part_decision.input_weight_kg,source_detail.input_weight_kg,source_detail.gross_weight_kg,source_detail.forging_weight_kg,0);
  required_steel:=round(production_pieces*input_weight,3);

  if production_pieces<=0 then raise exception 'Enter Accepted, Rejected or On Hold Part Production Quantity'; end if;
  if input_weight<=0 then raise exception 'Input Weight (kg/part) is required in Part Master supplier forging parameters'; end if;

  select coalesce(sum(coalesce(required_steel_quantity_kg,steel_quantity_kg,quantity_received,0)),0) into heat_allocated_steel
  from public.inward_lots where rmtc_approval_id=cert.id and (new.id is null or id<>new.id);
  if heat_allocated_steel+required_steel>cert.certificate_quantity then
    raise exception 'Cumulative heat production steel % kg exceeds RMTC steel quantity % kg',round(heat_allocated_steel+required_steel,3),cert.certificate_quantity;
  end if;

  select coalesce(sum(coalesce(production_quantity_pcs,0)),0) into part_allocated_pieces
  from public.inward_lots where rmtc_part_approval_id=part_decision.id and (new.id is null or id<>new.id);
  if part_decision.planned_production_quantity_pcs>0 and part_allocated_pieces+production_pieces>part_decision.planned_production_quantity_pcs then
    raise exception 'Cumulative production % pieces exceeds RMTC planned production % pieces for this Part Number',part_allocated_pieces+production_pieces,part_decision.planned_production_quantity_pcs;
  end if;

  select coalesce(sum(quantity_started),0) into batch_allocated_pieces
  from public.production_batches where inward_lot_id=new.id and parent_batch_id is null;
  if batch_allocated_pieces>production_pieces then
    raise exception 'Production quantity cannot be reduced below % pieces already allocated to production batches',batch_allocated_pieces;
  end if;

  if new.receipt_disposition='REJECTED' and (accepted_pieces>0 or hold_pieces>0 or rejected_pieces<=0) then
    raise exception 'Rejected inward requires only Rejected Production Quantity';
  elsif new.receipt_disposition='ON_HOLD' and (hold_pieces<=0 or nullif(btrim(coalesce(new.reserve_reason,'')),'') is null) then
    raise exception 'On Hold inward requires On Hold Production Quantity and reason';
  elsif new.receipt_disposition='ACCEPTED_UNDER_RESERVE' and (accepted_pieces<=0 or nullif(btrim(coalesce(new.reserve_reason,'')),'') is null) then
    raise exception 'Accepted Under Reserve requires Accepted Production Quantity and reason';
  elsif new.receipt_disposition='ACCEPTED' and accepted_pieces<=0 then
    raise exception 'Accepted inward requires Accepted Production Quantity';
  end if;

  new.rmtc_part_approval_id:=part_decision.id;
  new.part_id:=part_decision.part_id;
  new.supplier_id:=cert.supplier_id;
  new.heat_number:=cert.heat_number;
  new.heat_code:=cert.heat_code;
  new.rmtc_disposition:=part_decision.disposition;
  new.supplier_source_detail_id:=source_detail.id;
  new.input_weight_kg:=input_weight;
  new.accepted_production_quantity_pcs:=accepted_pieces;
  new.rejected_production_quantity_pcs:=rejected_pieces;
  new.hold_production_quantity_pcs:=hold_pieces;
  new.production_quantity_pcs:=production_pieces;
  new.accepted_steel_quantity_kg:=round(accepted_pieces*input_weight,3);
  new.rejected_steel_quantity_kg:=round(rejected_pieces*input_weight,3);
  new.hold_steel_quantity_kg:=round(hold_pieces*input_weight,3);
  new.required_steel_quantity_kg:=required_steel;
  new.steel_quantity_kg:=required_steel;
  new.quantity_received:=required_steel;
  new.quantity_accepted:=new.accepted_steel_quantity_kg;
  new.quantity_rejected:=new.rejected_steel_quantity_kg;

  if new.receipt_disposition='REJECTED' then
    new.status:='REJECTED';
  elsif new.receipt_disposition in ('PENDING','ON_HOLD','ACCEPTED_UNDER_RESERVE') then
    new.status:='HOLD_PENDING_INSPECTION';
  else
    new.status:=case when new.metallurgical_status in ('PASS','NOT_REQUIRED') and new.dimensional_status in ('PASS','NOT_REQUIRED') then 'RELEASED' else 'HOLD_PENDING_INSPECTION' end;
  end if;
  return new;
end;
$$;

-- Recreate accepted RMTC source view with both heat and part production balances.
drop view if exists public.v_qsms_accepted_rmtc_parts;
create view public.v_qsms_accepted_rmtc_parts as
select
  pa.id as rmtc_part_approval_id,
  pa.tenant_id,
  pa.rmtc_approval_id,
  pa.part_id,
  p.part_number,
  p.part_name,
  r.rmtc_number,
  r.certificate_reference,
  r.certificate_date,
  r.supplier_id,
  supplier.party_name as supplier_name,
  r.steel_mill_id,
  mill.party_name as steel_mill_name,
  p.material_grade_id,
  grade.grade_code as material_grade,
  r.heat_number,
  r.heat_code,
  r.certificate_quantity as rmtc_steel_quantity_kg,
  pa.disposition,
  pa.decision_reason,
  pa.planned_production_quantity_pcs,
  pa.input_weight_kg,
  pa.planned_steel_quantity_kg,
  src.id as supplier_source_detail_id,
  src.section_size,
  src.forging_route,
  src.forging_weight_kg,
  src.gross_weight_kg,
  coalesce(src.input_weight_kg,pa.input_weight_kg,src.gross_weight_kg,src.forging_weight_kg) as source_input_weight_kg,
  coalesce(part_alloc.production_quantity_pcs,0) as inward_production_quantity_pcs,
  greatest(pa.planned_production_quantity_pcs-coalesce(part_alloc.production_quantity_pcs,0),0) as available_production_quantity_pcs,
  coalesce(heat_alloc.steel_quantity_kg,0) as inward_steel_quantity_kg,
  greatest(r.certificate_quantity-coalesce(heat_alloc.steel_quantity_kg,0),0) as available_steel_quantity_kg,
  greatest(r.certificate_quantity-coalesce(heat_alloc.steel_quantity_kg,0),0) as available_quantity
from public.rmtc_part_approvals pa
join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
join public.parts p on p.id=pa.part_id
join public.parties supplier on supplier.id=r.supplier_id
join public.parties mill on mill.id=r.steel_mill_id
left join public.material_grades grade on grade.id=p.material_grade_id
left join lateral (
  select d.* from public.part_raw_material_details d
  where d.tenant_id=pa.tenant_id and d.part_id=pa.part_id and d.supplier_id=r.supplier_id and d.status='ACTIVE'
  order by case when d.id=r.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at
  limit 1
) src on true
left join lateral (
  select sum(coalesce(i.production_quantity_pcs,0)) as production_quantity_pcs
  from public.inward_lots i where i.rmtc_part_approval_id=pa.id
) part_alloc on true
left join lateral (
  select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as steel_quantity_kg
  from public.inward_lots i where i.rmtc_approval_id=r.id
) heat_alloc on true
where r.status in ('APPROVED','PARTIALLY_APPROVED')
  and r.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
  and pa.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE');

create or replace view public.v_qsms_heat_production_summary as
select
  r.id as rmtc_approval_id,
  r.tenant_id,
  r.rmtc_number,
  r.heat_number,
  r.heat_code,
  r.certificate_quantity as rmtc_steel_quantity_kg,
  coalesce(sum(pa.planned_steel_quantity_kg),0) as planned_steel_quantity_kg,
  coalesce((select sum(i.required_steel_quantity_kg) from public.inward_lots i where i.rmtc_approval_id=r.id),0) as inward_steel_quantity_kg,
  greatest(r.certificate_quantity-coalesce((select sum(i.required_steel_quantity_kg) from public.inward_lots i where i.rmtc_approval_id=r.id),0),0) as available_steel_quantity_kg,
  coalesce((select sum(i.accepted_production_quantity_pcs) from public.inward_lots i where i.rmtc_approval_id=r.id),0) as accepted_production_quantity_pcs,
  coalesce((select sum(i.rejected_production_quantity_pcs) from public.inward_lots i where i.rmtc_approval_id=r.id),0) as rejected_production_quantity_pcs,
  coalesce((select sum(i.hold_production_quantity_pcs) from public.inward_lots i where i.rmtc_approval_id=r.id),0) as hold_production_quantity_pcs
from public.rmtc_approvals r
left join public.rmtc_part_approvals pa on pa.rmtc_approval_id=r.id
group by r.id;

commit;
