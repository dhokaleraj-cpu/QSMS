-- QSMS 4.8.3 — Heat Number search, reusable rejected heat and global steel ledger.
-- Existing records are preserved. All quantities are validated globally across the same Heat Number.
begin;

create or replace function public.qsms_normalize_heat_number(p_heat_number text)
returns text
language sql
immutable
set search_path=public
as $$
  select upper(regexp_replace(btrim(coalesce(p_heat_number,'')),'[^A-Za-z0-9]','','g'));
$$;

alter table public.rmtc_approvals
  add column if not exists normalized_heat_number text;

update public.rmtc_approvals
set normalized_heat_number=public.qsms_normalize_heat_number(heat_number)
where normalized_heat_number is distinct from public.qsms_normalize_heat_number(heat_number);

create index if not exists idx_rmtc_normalized_heat
  on public.rmtc_approvals(tenant_id,normalized_heat_number,status,disposition);

create or replace function public.enforce_rmtc_heat_identity()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_global_quantity numeric;
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
  return new;
end;
$$;

drop trigger if exists trg_rmtc_heat_identity on public.rmtc_approvals;
create trigger trg_rmtc_heat_identity
before insert or update of heat_number,certificate_quantity
on public.rmtc_approvals
for each row execute function public.enforce_rmtc_heat_identity();

create or replace function public.enforce_heat_part_supplier_duplicate()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
begin
  select * into v_header from public.rmtc_approvals where id=new.rmtc_approval_id;
  if v_header.id is null then raise exception 'Linked RMTC header does not exist'; end if;

  if exists(
    select 1
    from public.rmtc_part_approvals other_pa
    join public.rmtc_approvals other_r on other_r.id=other_pa.rmtc_approval_id
    where other_r.tenant_id=v_header.tenant_id
      and other_r.normalized_heat_number=v_header.normalized_heat_number
      and other_r.id<>v_header.id
      and other_r.supplier_id=v_header.supplier_id
      and other_pa.part_id=new.part_id
      and other_r.status not in ('REJECTED','SUPERSEDED')
      and coalesce(other_r.disposition,'PENDING')<>'REJECTED'
  ) then
    raise exception 'This Heat Number already has an active RMTC for the same Supplier and Part Number. Reuse is allowed after rejection, or select a different Supplier or Part Number.';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_heat_part_supplier_duplicate on public.rmtc_part_approvals;
create trigger trg_heat_part_supplier_duplicate
before insert or update of rmtc_approval_id,part_id
on public.rmtc_part_approvals
for each row execute function public.enforce_heat_part_supplier_duplicate();

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
  other_planned_steel numeric:=0;
  inward_pieces numeric:=0;
  planned_pieces numeric:=coalesce(new.planned_production_quantity_pcs,0);
  input_weight numeric;
begin
  select * into header_row from public.rmtc_approvals where id=new.rmtc_approval_id;
  if header_row.id is null then raise exception 'Linked RMTC header does not exist'; end if;

  select max(certificate_quantity) into global_quantity
  from public.rmtc_approvals
  where tenant_id=header_row.tenant_id and normalized_heat_number=header_row.normalized_heat_number;

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

  select coalesce(sum(coalesce(pa.planned_steel_quantity_kg,0)),0) into other_planned_steel
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  where r.tenant_id=header_row.tenant_id
    and r.normalized_heat_number=header_row.normalized_heat_number
    and pa.id<>new.id
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  if header_row.status not in ('REJECTED','SUPERSEDED')
     and coalesce(header_row.disposition,'PENDING')<>'REJECTED'
     and other_planned_steel+new.planned_steel_quantity_kg>global_quantity then
    raise exception 'Global planned steel % kg for Heat % exceeds the Heat steel quantity % kg',
      round(other_planned_steel+new.planned_steel_quantity_kg,3),header_row.heat_number,global_quantity;
  end if;

  select coalesce(sum(coalesce(production_quantity_pcs,0)),0) into inward_pieces
  from public.inward_lots where rmtc_part_approval_id=new.id;
  if planned_pieces<inward_pieces then
    raise exception 'Planned production quantity cannot be reduced below % pieces already inwarded',inward_pieces;
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
  v_other_inward numeric:=0;
  v_current_required numeric:=0;
begin
  select * into v_header from public.rmtc_approvals where id=new.rmtc_approval_id;
  if v_header.id is null then return new; end if;

  select max(certificate_quantity) into v_global_quantity
  from public.rmtc_approvals
  where tenant_id=v_header.tenant_id and normalized_heat_number=v_header.normalized_heat_number;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
  into v_other_inward
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=v_header.tenant_id
    and r.normalized_heat_number=v_header.normalized_heat_number
    and (new.id is null or i.id<>new.id);

  v_current_required:=coalesce(new.required_steel_quantity_kg,new.steel_quantity_kg,new.quantity_received,0);
  if v_other_inward+v_current_required>v_global_quantity then
    raise exception 'Global inward steel % kg for Heat % exceeds the Heat steel quantity % kg',
      round(v_other_inward+v_current_required,3),v_header.heat_number,v_global_quantity;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_global_heat_inward_limit on public.inward_lots;
create trigger trg_global_heat_inward_limit
after insert or update of rmtc_approval_id,required_steel_quantity_kg,steel_quantity_kg,quantity_received
on public.inward_lots
for each row execute function public.enforce_global_heat_inward_limit();

-- Heat-level summary used by the RMTC search and dashboard.
drop view if exists public.v_qsms_heat_summary;
create view public.v_qsms_heat_summary with (security_invoker=true) as
select
  r.tenant_id,
  r.normalized_heat_number,
  min(r.heat_number) as heat_number,
  max(r.certificate_quantity) as global_steel_quantity_kg,
  count(distinct r.id) as rmtc_count,
  count(distinct r.id) filter(where r.status in ('REJECTED','SUPERSEDED') or r.disposition='REJECTED') as rejected_rmtc_count,
  count(distinct r.id) filter(where r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED') as active_rmtc_count,
  coalesce(sum(pa.planned_steel_quantity_kg) filter(where r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED'),0) as active_planned_steel_quantity_kg,
  coalesce((
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0))
    from public.inward_lots i
    join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id
    where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number
  ),0) as inward_steel_quantity_kg,
  greatest(max(r.certificate_quantity)-coalesce((
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0))
    from public.inward_lots i
    join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id
    where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number
  ),0),0) as available_steel_quantity_kg,
  max(r.updated_at) as last_activity_at
from public.rmtc_approvals r
left join public.rmtc_part_approvals pa on pa.rmtc_approval_id=r.id
group by r.tenant_id,r.normalized_heat_number;

-- One row per Part Number and RMTC for the searched Heat Number.
drop view if exists public.v_qsms_heat_rmtc_usage;
create view public.v_qsms_heat_rmtc_usage with (security_invoker=true) as
select
  r.tenant_id,
  r.normalized_heat_number,
  r.heat_number,
  r.id as rmtc_approval_id,
  r.rmtc_number,
  r.status as rmtc_status,
  r.disposition as rmtc_disposition,
  r.certificate_quantity as rmtc_steel_quantity_kg,
  r.supplier_id,
  supplier.party_name as supplier_name,
  pa.id as rmtc_part_approval_id,
  pa.part_id,
  p.part_number,
  p.part_name,
  pa.approval_status as automated_validation,
  pa.disposition as part_disposition,
  pa.planned_production_quantity_pcs,
  pa.input_weight_kg,
  pa.planned_steel_quantity_kg,
  coalesce((select sum(i.production_quantity_pcs) from public.inward_lots i where i.rmtc_part_approval_id=pa.id),0) as inward_production_quantity_pcs,
  coalesce((select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) from public.inward_lots i where i.rmtc_part_approval_id=pa.id),0) as inward_steel_quantity_kg,
  r.created_at,
  r.updated_at
from public.rmtc_approvals r
join public.parties supplier on supplier.id=r.supplier_id
left join public.rmtc_part_approvals pa on pa.rmtc_approval_id=r.id
left join public.parts p on p.id=pa.part_id;

-- Compatibility summary remains one row per RMTC, but quantities are global for the Heat Number.
drop view if exists public.v_qsms_heat_production_summary;
create view public.v_qsms_heat_production_summary with (security_invoker=true) as
select
  r.id as rmtc_approval_id,
  r.tenant_id,
  r.rmtc_number,
  r.heat_number,
  r.normalized_heat_number,
  r.heat_code,
  hs.global_steel_quantity_kg as rmtc_steel_quantity_kg,
  hs.active_planned_steel_quantity_kg as planned_steel_quantity_kg,
  hs.inward_steel_quantity_kg,
  hs.available_steel_quantity_kg,
  coalesce((select sum(i.accepted_production_quantity_pcs) from public.inward_lots i join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number),0) as accepted_production_quantity_pcs,
  coalesce((select sum(i.rejected_production_quantity_pcs) from public.inward_lots i join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number),0) as rejected_production_quantity_pcs,
  coalesce((select sum(i.hold_production_quantity_pcs) from public.inward_lots i join public.rmtc_approvals ri on ri.id=i.rmtc_approval_id where ri.tenant_id=r.tenant_id and ri.normalized_heat_number=r.normalized_heat_number),0) as hold_production_quantity_pcs
from public.rmtc_approvals r
join public.v_qsms_heat_summary hs on hs.tenant_id=r.tenant_id and hs.normalized_heat_number=r.normalized_heat_number;

-- Accepted RMTC part list now exposes the global Heat balance.
drop view if exists public.v_qsms_accepted_rmtc_parts;
create view public.v_qsms_accepted_rmtc_parts with (security_invoker=true) as
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
  r.normalized_heat_number,
  r.heat_code,
  hs.global_steel_quantity_kg as rmtc_steel_quantity_kg,
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
  hs.inward_steel_quantity_kg,
  hs.available_steel_quantity_kg,
  hs.available_steel_quantity_kg as available_quantity
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
  order by case when d.id=r.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at
  limit 1
) src on true
left join lateral (
  select sum(coalesce(i.production_quantity_pcs,0)) as production_quantity_pcs
  from public.inward_lots i where i.rmtc_part_approval_id=pa.id
) part_alloc on true
where r.status in ('APPROVED','PARTIALLY_APPROVED')
  and r.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
  and pa.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE');

grant select on public.v_qsms_heat_summary to authenticated;
grant select on public.v_qsms_heat_rmtc_usage to authenticated;
grant select on public.v_qsms_heat_production_summary to authenticated;
grant select on public.v_qsms_accepted_rmtc_parts to authenticated;

commit;
