-- QSMS 4.8.5 — Combined Heat steel commitment and entry-balance protection.
-- Heat capacity is protected by inward steel already consumed plus the still-unconsumed
-- portion of every active RMTC production plan for the same normalized Heat Number.
-- Existing records are preserved.
begin;

create or replace function public.enforce_rmtc_heat_identity()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_global_quantity numeric;
  v_inward_steel numeric:=0;
  v_remaining_planned numeric:=0;
  v_committed numeric:=0;
begin
  new.normalized_heat_number:=public.qsms_normalize_heat_number(new.heat_number);
  if new.normalized_heat_number='' then raise exception 'Heat Number is required'; end if;

  select max(certificate_quantity) into v_global_quantity
  from public.rmtc_approvals
  where tenant_id=new.tenant_id
    and normalized_heat_number=new.normalized_heat_number
    and id<>new.id;

  if v_global_quantity is not null and abs(coalesce(new.certificate_quantity,0)-v_global_quantity)>0.001 then
    raise exception 'Heat Number % already has a global steel quantity of % kg. Use the same quantity for every RMTC under this heat.',new.heat_number,v_global_quantity;
  end if;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into v_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into v_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  v_committed:=v_inward_steel+v_remaining_planned;
  if coalesce(new.certificate_quantity,0)+0.001<v_committed then
    raise exception 'Heat steel quantity % kg cannot be lower than committed Heat steel % kg (Inward % kg + Remaining planned % kg)',
      round(coalesce(new.certificate_quantity,0),3),round(v_committed,3),round(v_inward_steel,3),round(v_remaining_planned,3);
  end if;
  return new;
end;
$$;

create or replace function public.enforce_rmtc_certificate_production_limit()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_normalized text:=coalesce(new.normalized_heat_number,public.qsms_normalize_heat_number(new.heat_number));
  v_inward_steel numeric:=0;
  v_remaining_planned numeric:=0;
  v_committed numeric:=0;
begin
  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into v_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=new.tenant_id and r.normalized_heat_number=v_normalized;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into v_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=new.tenant_id and r.normalized_heat_number=v_normalized
    and r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED';

  v_committed:=v_inward_steel+v_remaining_planned;
  if new.certificate_quantity+0.001<v_committed then
    raise exception 'Global Heat steel quantity cannot be reduced below committed steel % kg (Inward % kg + Remaining planned % kg)',
      round(v_committed,3),round(v_inward_steel,3),round(v_remaining_planned,3);
  end if;
  return new;
end;
$$;

create or replace function public.enforce_rmtc_part_production_plan()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  header_row public.rmtc_approvals%rowtype;
  source_row public.part_raw_material_details%rowtype;
  global_quantity numeric:=0;
  heat_inward_steel numeric:=0;
  current_part_inward_steel numeric:=0;
  current_part_inward_pieces numeric:=0;
  other_remaining_planned numeric:=0;
  projected_current_remaining numeric:=0;
  projected_commitment numeric:=0;
  planned_pieces numeric:=coalesce(new.planned_production_quantity_pcs,0);
  input_weight numeric;
begin
  select * into header_row from public.rmtc_approvals where id=new.rmtc_approval_id;
  if header_row.id is null then raise exception 'Linked RMTC header does not exist'; end if;

  select max(certificate_quantity) into global_quantity
  from public.rmtc_approvals
  where tenant_id=header_row.tenant_id and normalized_heat_number=header_row.normalized_heat_number;
  global_quantity:=coalesce(global_quantity,header_row.certificate_quantity,0);

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

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0),
         coalesce(sum(coalesce(i.production_quantity_pcs,0)),0)
    into current_part_inward_steel,current_part_inward_pieces
  from public.inward_lots i where i.rmtc_part_approval_id=new.id;

  if planned_pieces<current_part_inward_pieces then
    raise exception 'Planned production quantity cannot be reduced below % pieces already inwarded',current_part_inward_pieces;
  end if;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into heat_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=header_row.tenant_id and r.normalized_heat_number=header_row.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into other_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=header_row.tenant_id
    and r.normalized_heat_number=header_row.normalized_heat_number
    and pa.id<>new.id
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  projected_current_remaining:=case
    when header_row.status in ('REJECTED','SUPERSEDED') or coalesce(header_row.disposition,'PENDING')='REJECTED' then 0
    else greatest(new.planned_steel_quantity_kg-current_part_inward_steel,0)
  end;
  projected_commitment:=heat_inward_steel+other_remaining_planned+projected_current_remaining;

  if projected_commitment>global_quantity+0.001 then
    raise exception 'Committed Heat steel % kg exceeds Heat steel quantity % kg (Inward % kg + Remaining planned % kg)',
      round(projected_commitment,3),round(global_quantity,3),round(heat_inward_steel,3),
      round(other_remaining_planned+projected_current_remaining,3);
  end if;
  return new;
end;
$$;

create or replace function public.enforce_global_heat_inward_limit()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
  v_global_quantity numeric:=0;
  v_inward_steel numeric:=0;
  v_remaining_planned numeric:=0;
  v_committed numeric:=0;
begin
  select * into v_header from public.rmtc_approvals where id=new.rmtc_approval_id;
  if v_header.id is null then return new; end if;

  select max(certificate_quantity) into v_global_quantity
  from public.rmtc_approvals
  where tenant_id=v_header.tenant_id and normalized_heat_number=v_header.normalized_heat_number;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into v_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=v_header.tenant_id and r.normalized_heat_number=v_header.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into v_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=v_header.tenant_id
    and r.normalized_heat_number=v_header.normalized_heat_number
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  v_committed:=v_inward_steel+v_remaining_planned;
  if v_committed>v_global_quantity+0.001 then
    raise exception 'Committed Heat steel % kg exceeds Heat steel quantity % kg after Material Inward (Inward % kg + Remaining planned % kg)',
      round(v_committed,3),round(v_global_quantity,3),round(v_inward_steel,3),round(v_remaining_planned,3);
  end if;
  return new;
end;
$$;

-- Keep the existing AFTER trigger, but point it at the combined commitment rule.
drop trigger if exists trg_global_heat_inward_limit on public.inward_lots;
create trigger trg_global_heat_inward_limit
after insert or update of rmtc_approval_id,required_steel_quantity_kg,steel_quantity_kg,quantity_received,production_quantity_pcs
on public.inward_lots
for each row execute function public.enforce_global_heat_inward_limit();

-- Heat-level summary: inward steel plus only the unconsumed portion of active plans.
drop view if exists public.v_qsms_heat_summary cascade;
create view public.v_qsms_heat_summary with (security_invoker=true) as
with headers as (
  select
    tenant_id,normalized_heat_number,min(heat_number) as heat_number,
    max(certificate_quantity) as global_steel_quantity_kg,
    count(distinct id) as rmtc_count,
    count(distinct id) filter(where status in ('REJECTED','SUPERSEDED') or disposition='REJECTED') as rejected_rmtc_count,
    count(distinct id) filter(where status not in ('REJECTED','SUPERSEDED') and coalesce(disposition,'PENDING')<>'REJECTED') as active_rmtc_count,
    max(updated_at) as last_activity_at
  from public.rmtc_approvals
  group by tenant_id,normalized_heat_number
), part_usage as (
  select
    r.tenant_id,r.normalized_heat_number,pa.id as rmtc_part_approval_id,
    coalesce(pa.planned_steel_quantity_kg,0) as planned_steel_quantity_kg,
    coalesce((
      select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0))
      from public.inward_lots i where i.rmtc_part_approval_id=pa.id
    ),0) as inward_part_steel_quantity_kg
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  where r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED'
), plans as (
  select
    tenant_id,normalized_heat_number,
    coalesce(sum(planned_steel_quantity_kg),0) as active_planned_steel_quantity_kg,
    coalesce(sum(greatest(planned_steel_quantity_kg-inward_part_steel_quantity_kg,0)),0) as remaining_planned_steel_quantity_kg
  from part_usage group by tenant_id,normalized_heat_number
), inward as (
  select
    r.tenant_id,r.normalized_heat_number,
    coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0) as inward_steel_quantity_kg
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  group by r.tenant_id,r.normalized_heat_number
)
select
  h.tenant_id,h.normalized_heat_number,h.heat_number,h.global_steel_quantity_kg,
  h.rmtc_count,h.rejected_rmtc_count,h.active_rmtc_count,
  coalesce(p.active_planned_steel_quantity_kg,0) as active_planned_steel_quantity_kg,
  coalesce(i.inward_steel_quantity_kg,0) as inward_steel_quantity_kg,
  coalesce(p.remaining_planned_steel_quantity_kg,0) as remaining_planned_steel_quantity_kg,
  coalesce(i.inward_steel_quantity_kg,0)+coalesce(p.remaining_planned_steel_quantity_kg,0) as committed_steel_quantity_kg,
  greatest(h.global_steel_quantity_kg-coalesce(i.inward_steel_quantity_kg,0)-coalesce(p.remaining_planned_steel_quantity_kg,0),0) as available_unallocated_steel_quantity_kg,
  greatest(h.global_steel_quantity_kg-coalesce(i.inward_steel_quantity_kg,0)-coalesce(p.remaining_planned_steel_quantity_kg,0),0) as available_steel_quantity_kg,
  h.last_activity_at
from headers h
left join plans p on p.tenant_id=h.tenant_id and p.normalized_heat_number=h.normalized_heat_number
left join inward i on i.tenant_id=h.tenant_id and i.normalized_heat_number=h.normalized_heat_number;

-- One row per Part Number/RMTC with planned, consumed and remaining reservation.
drop view if exists public.v_qsms_heat_rmtc_usage;
create view public.v_qsms_heat_rmtc_usage with (security_invoker=true) as
select
  r.tenant_id,r.normalized_heat_number,r.heat_number,r.id as rmtc_approval_id,
  r.rmtc_number,r.status as rmtc_status,r.disposition as rmtc_disposition,
  r.certificate_quantity as rmtc_steel_quantity_kg,r.supplier_id,supplier.party_name as supplier_name,
  pa.id as rmtc_part_approval_id,pa.part_id,p.part_number,p.part_name,
  pa.approval_status as automated_validation,pa.disposition as part_disposition,
  pa.planned_production_quantity_pcs,pa.input_weight_kg,pa.planned_steel_quantity_kg,
  coalesce(part_inward.production_quantity_pcs,0) as inward_production_quantity_pcs,
  coalesce(part_inward.inward_steel_quantity_kg,0) as inward_steel_quantity_kg,
  greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel_quantity_kg,0),0) as remaining_planned_steel_quantity_kg,
  r.created_at,r.updated_at
from public.rmtc_approvals r
join public.parties supplier on supplier.id=r.supplier_id
left join public.rmtc_part_approvals pa on pa.rmtc_approval_id=r.id
left join public.parts p on p.id=pa.part_id
left join lateral (
  select
    sum(coalesce(i.production_quantity_pcs,0)) as production_quantity_pcs,
    sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel_quantity_kg
  from public.inward_lots i where i.rmtc_part_approval_id=pa.id
) part_inward on true;

-- Accepted source list exposes both unallocated Heat balance and the selected part reservation.
create view public.v_qsms_accepted_rmtc_parts with (security_invoker=true) as
select
  pa.id as rmtc_part_approval_id,pa.tenant_id,pa.rmtc_approval_id,pa.part_id,
  p.part_number,p.part_name,r.rmtc_number,r.certificate_reference,r.certificate_date,
  r.supplier_id,supplier.party_name as supplier_name,r.steel_mill_id,mill.party_name as steel_mill_name,
  p.material_grade_id,grade.grade_code as material_grade,r.heat_number,r.normalized_heat_number,r.heat_code,
  hs.global_steel_quantity_kg as rmtc_steel_quantity_kg,pa.disposition,pa.decision_reason,
  pa.planned_production_quantity_pcs,pa.input_weight_kg,pa.planned_steel_quantity_kg,
  src.id as supplier_source_detail_id,src.section_size,src.forging_route,src.forging_weight_kg,src.gross_weight_kg,
  coalesce(src.input_weight_kg,pa.input_weight_kg,src.gross_weight_kg,src.forging_weight_kg) as source_input_weight_kg,
  coalesce(part_alloc.production_quantity_pcs,0) as inward_production_quantity_pcs,
  greatest(pa.planned_production_quantity_pcs-coalesce(part_alloc.production_quantity_pcs,0),0) as available_production_quantity_pcs,
  coalesce(part_alloc.inward_steel_quantity_kg,0) as part_inward_steel_quantity_kg,
  greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_alloc.inward_steel_quantity_kg,0),0) as part_remaining_planned_steel_quantity_kg,
  greatest(coalesce(hs.remaining_planned_steel_quantity_kg,0)-greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_alloc.inward_steel_quantity_kg,0),0),0) as other_remaining_planned_steel_quantity_kg,
  hs.inward_steel_quantity_kg,
  hs.remaining_planned_steel_quantity_kg as heat_remaining_planned_steel_quantity_kg,
  hs.committed_steel_quantity_kg as heat_committed_steel_quantity_kg,
  hs.available_unallocated_steel_quantity_kg as heat_unallocated_balance_kg,
  greatest(
    hs.global_steel_quantity_kg-hs.inward_steel_quantity_kg-
    greatest(coalesce(hs.remaining_planned_steel_quantity_kg,0)-greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_alloc.inward_steel_quantity_kg,0),0),0),0
  ) as available_steel_for_selected_entry_kg,
  greatest(
    hs.global_steel_quantity_kg-hs.inward_steel_quantity_kg-
    greatest(coalesce(hs.remaining_planned_steel_quantity_kg,0)-greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_alloc.inward_steel_quantity_kg,0),0),0),0
  ) as available_steel_quantity_kg,
  greatest(
    hs.global_steel_quantity_kg-hs.inward_steel_quantity_kg-
    greatest(coalesce(hs.remaining_planned_steel_quantity_kg,0)-greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_alloc.inward_steel_quantity_kg,0),0),0),0
  ) as available_quantity
from public.rmtc_part_approvals pa
join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
join public.v_qsms_heat_summary hs on hs.tenant_id=r.tenant_id and hs.normalized_heat_number=r.normalized_heat_number
join public.parts p on p.id=pa.part_id
join public.parties supplier on supplier.id=r.supplier_id
join public.parties mill on mill.id=r.steel_mill_id
left join public.material_grades grade on grade.id=p.material_grade_id
left join lateral (
  select d.* from public.part_raw_material_details d
  where d.tenant_id=pa.tenant_id and d.part_id=pa.part_id and d.supplier_id=r.supplier_id and d.status='ACTIVE'
  order by case when d.id=r.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at limit 1
) src on true
left join lateral (
  select
    sum(coalesce(i.production_quantity_pcs,0)) as production_quantity_pcs,
    sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel_quantity_kg
  from public.inward_lots i where i.rmtc_part_approval_id=pa.id
) part_alloc on true
where r.status in ('APPROVED','PARTIALLY_APPROVED')
  and r.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
  and pa.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE');

create or replace view public.v_qsms_heat_production_summary with (security_invoker=true) as
select
  r.id as rmtc_approval_id,r.tenant_id,r.rmtc_number,r.heat_number,r.normalized_heat_number,r.heat_code,
  hs.global_steel_quantity_kg as rmtc_steel_quantity_kg,
  hs.active_planned_steel_quantity_kg as planned_steel_quantity_kg,
  hs.remaining_planned_steel_quantity_kg,
  hs.inward_steel_quantity_kg,
  hs.committed_steel_quantity_kg,
  hs.available_unallocated_steel_quantity_kg,
  hs.available_steel_quantity_kg,
  coalesce((select sum(i.accepted_production_quantity_pcs) from public.inward_lots i join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number),0) as accepted_production_quantity_pcs,
  coalesce((select sum(i.rejected_production_quantity_pcs) from public.inward_lots i join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number),0) as rejected_production_quantity_pcs,
  coalesce((select sum(i.hold_production_quantity_pcs) from public.inward_lots i join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number),0) as hold_production_quantity_pcs
from public.rmtc_approvals r
join public.v_qsms_heat_summary hs on hs.tenant_id=r.tenant_id and hs.normalized_heat_number=r.normalized_heat_number;

grant select on public.v_qsms_heat_summary to authenticated;
grant select on public.v_qsms_heat_rmtc_usage to authenticated;
grant select on public.v_qsms_accepted_rmtc_parts to authenticated;
grant select on public.v_qsms_heat_production_summary to authenticated;

commit;
