-- QSMS 4.8.0: steel-to-production quantity control, supplier source snapshot,
-- automatic inspection layout metadata and RMTC-style raw material MetLAB results.
begin;

alter table public.part_raw_material_details
  add column if not exists input_weight_kg numeric;
update public.part_raw_material_details
   set input_weight_kg=coalesce(input_weight_kg,gross_weight_kg,forging_weight_kg)
 where input_weight_kg is null;
alter table public.part_raw_material_details drop constraint if exists part_raw_material_details_input_weight_check;
alter table public.part_raw_material_details add constraint part_raw_material_details_input_weight_check
  check (input_weight_kg is null or input_weight_kg>0);

alter table public.inward_lots
  add column if not exists steel_quantity_kg numeric,
  add column if not exists production_quantity_pcs numeric,
  add column if not exists input_weight_kg numeric,
  add column if not exists required_steel_quantity_kg numeric,
  add column if not exists supplier_source_detail_id uuid references public.part_raw_material_details(id);
update public.inward_lots
   set steel_quantity_kg=coalesce(steel_quantity_kg,quantity_received),
       production_quantity_pcs=coalesce(production_quantity_pcs,0),
       required_steel_quantity_kg=coalesce(required_steel_quantity_kg,0)
 where steel_quantity_kg is null or production_quantity_pcs is null or required_steel_quantity_kg is null;
alter table public.inward_lots drop constraint if exists inward_lots_steel_quantity_check;
alter table public.inward_lots add constraint inward_lots_steel_quantity_check
  check (steel_quantity_kg is null or steel_quantity_kg>0);
alter table public.inward_lots drop constraint if exists inward_lots_production_quantity_check;
alter table public.inward_lots add constraint inward_lots_production_quantity_check
  check (production_quantity_pcs is null or production_quantity_pcs>=0);
alter table public.inward_lots drop constraint if exists inward_lots_input_weight_check;
alter table public.inward_lots add constraint inward_lots_input_weight_check
  check (input_weight_kg is null or input_weight_kg>0);
alter table public.inward_lots drop constraint if exists inward_lots_required_steel_check;
alter table public.inward_lots add constraint inward_lots_required_steel_check
  check (required_steel_quantity_kg is null or required_steel_quantity_kg>=0);

alter table public.inspection_reports
  add column if not exists layout_name_snapshot text,
  add column if not exists layout_type_name text,
  add column if not exists steel_quantity_kg numeric,
  add column if not exists production_quantity_pcs numeric;

alter table public.lab_tests
  add column if not exists rmtc_approval_id uuid references public.rmtc_approvals(id),
  add column if not exists supplier_id uuid references public.parties(id),
  add column if not exists steel_mill_id uuid references public.parties(id),
  add column if not exists material_grade_id uuid references public.material_grades(id),
  add column if not exists layout_name_snapshot text,
  add column if not exists layout_type_name text,
  add column if not exists steel_quantity_kg numeric,
  add column if not exists production_quantity_pcs numeric;

create index if not exists idx_inward_lots_rmtc_steel on public.inward_lots(rmtc_approval_id,steel_quantity_kg);
create index if not exists idx_inspection_plan_auto_match on public.inspection_plans(part_id,layout_type,process_id,inspection_stage_id,status,effective_date desc);

drop view if exists public.v_qsms_accepted_rmtc_parts;
create view public.v_qsms_accepted_rmtc_parts
with (security_invoker=true)
as
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
  r.certificate_quantity,
  r.certificate_quantity as rmtc_steel_quantity_kg,
  pa.disposition,
  pa.decision_reason,
  src.id as supplier_source_detail_id,
  coalesce(src.input_weight_kg,src.gross_weight_kg,src.forging_weight_kg) as input_weight_kg,
  src.forging_weight_kg,
  src.gross_weight_kg,
  src.section_size,
  src.forging_route,
  greatest(
    r.certificate_quantity-coalesce((
      select sum(coalesce(i.steel_quantity_kg,i.quantity_received))
        from public.inward_lots i where i.rmtc_approval_id=r.id
    ),0),0
  ) as available_quantity,
  greatest(
    r.certificate_quantity-coalesce((
      select sum(coalesce(i.steel_quantity_kg,i.quantity_received))
        from public.inward_lots i where i.rmtc_approval_id=r.id
    ),0),0
  ) as available_steel_quantity_kg
from public.rmtc_part_approvals pa
join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
join public.parts p on p.id=pa.part_id
join public.parties supplier on supplier.id=r.supplier_id
join public.parties mill on mill.id=r.steel_mill_id
left join public.material_grades grade on grade.id=p.material_grade_id
left join lateral (
  select d.* from public.part_raw_material_details d
   where d.tenant_id=pa.tenant_id and d.part_id=pa.part_id
     and d.supplier_id=r.supplier_id and d.status='ACTIVE'
   order by case when d.id=r.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at
   limit 1
) src on true
where r.status in ('APPROVED','PARTIALLY_APPROVED')
  and r.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
  and pa.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE');

grant select on public.v_qsms_accepted_rmtc_parts to authenticated;

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
  already_received numeric;
  allocated_to_batches numeric;
  steel_qty numeric;
  production_qty numeric;
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
     where id=new.supplier_source_detail_id and tenant_id=new.tenant_id
       and part_id=part_decision.part_id and supplier_id=cert.supplier_id and status='ACTIVE';
  end if;
  if source_detail.id is null then
    select * into source_detail from public.part_raw_material_details
     where tenant_id=new.tenant_id and part_id=part_decision.part_id
       and supplier_id=cert.supplier_id and status='ACTIVE'
     order by case when id=cert.selected_source_detail_id then 0 else 1 end,sequence_no,created_at limit 1;
  end if;
  if source_detail.id is null then
    raise exception 'Active supplier forging parameters are required in Part Master';
  end if;

  steel_qty:=coalesce(new.steel_quantity_kg,new.quantity_received,0);
  production_qty:=coalesce(new.production_quantity_pcs,0);
  input_weight:=coalesce(new.input_weight_kg,source_detail.input_weight_kg,source_detail.gross_weight_kg,source_detail.forging_weight_kg,0);
  required_steel:=round(production_qty*input_weight,3);

  if steel_qty<=0 then raise exception 'Steel Quantity (kg) must be greater than zero'; end if;
  if production_qty<=0 then raise exception 'Part Production Quantity must be greater than zero'; end if;
  if input_weight<=0 then raise exception 'Input Weight (kg/part) is required in Part Master supplier forging parameters'; end if;
  if required_steel>steel_qty then
    raise exception 'Required production steel quantity % kg exceeds inward steel quantity % kg',required_steel,steel_qty;
  end if;

  new.rmtc_part_approval_id:=part_decision.id;
  new.part_id:=part_decision.part_id;
  new.supplier_id:=cert.supplier_id;
  new.heat_number:=cert.heat_number;
  new.heat_code:=cert.heat_code;
  new.rmtc_disposition:=part_decision.disposition;
  new.supplier_source_detail_id:=source_detail.id;
  new.input_weight_kg:=input_weight;
  new.production_quantity_pcs:=production_qty;
  new.required_steel_quantity_kg:=required_steel;
  new.steel_quantity_kg:=steel_qty;
  new.quantity_received:=steel_qty;

  select coalesce(sum(coalesce(steel_quantity_kg,quantity_received)),0) into already_received
    from public.inward_lots
   where rmtc_approval_id=cert.id and (new.id is null or id<>new.id);
  if already_received+steel_qty>cert.certificate_quantity then
    raise exception 'Material inward steel quantity exceeds the available RMTC steel balance';
  end if;

  select coalesce(sum(quantity_started),0) into allocated_to_batches
    from public.production_batches where inward_lot_id=new.id and parent_batch_id is null;
  if allocated_to_batches>production_qty then
    raise exception 'Part Production Quantity cannot be reduced below % pieces already allocated to production batches',allocated_to_batches;
  end if;

  if new.receipt_disposition='REJECTED' then
    new.quantity_accepted:=0;new.quantity_rejected:=steel_qty;new.status:='REJECTED';
  elsif new.receipt_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then
    if nullif(btrim(coalesce(new.reserve_reason,'')),'') is null then
      raise exception 'Reason is mandatory for On Hold or Accepted Under Reserve inward';
    end if;
    new.status:='HOLD_PENDING_INSPECTION';
  elsif new.receipt_disposition='ACCEPTED' then
    new.quantity_accepted:=case when new.quantity_accepted=0 then steel_qty-new.quantity_rejected else new.quantity_accepted end;
    new.status:=case when new.metallurgical_status in ('PASS','NOT_REQUIRED') and new.dimensional_status in ('PASS','NOT_REQUIRED') then 'RELEASED' else 'HOLD_PENDING_INSPECTION' end;
  else
    new.status:='HOLD_PENDING_INSPECTION';
  end if;
  return new;
end;
$$;

create or replace function public.qsms_finalize_metlab_report(
  p_report_id uuid,p_disposition text,p_reason text,
  p_validated_by_employee_id uuid,p_approved_by_employee_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_report public.lab_tests%rowtype;
  v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_'));
  v_bad integer:=0;
begin
  if not public.qsms_has_module_approve('METLAB_REPORT') then raise exception 'MetLAB Report approval permission is required'; end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.lab_tests where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'MetLAB report was not found'; end if;

  select count(*) into v_bad from (
    select coalesce(item->>'result','NOT_EVALUATED') result from jsonb_array_elements(coalesce(v_report.results->'rows','[]'::jsonb)) item
    union all
    select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'chemistry_rows','[]'::jsonb)) item
    union all
    select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'jominy_rows','[]'::jsonb)) item
    union all
    select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'requirement_rows','[]'::jsonb)) item
  ) evaluated where result not in ('PASS','NOT_APPLICABLE');

  if v_disposition='ACCEPTED' and v_bad>0 and btrim(coalesce(p_reason,''))='' then
    raise exception 'Manual acceptance reason is mandatory when applicable MetLAB results do not all pass';
  end if;
  update public.lab_tests set disposition=v_disposition,
    disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,
    approved_by_employee_id=p_approved_by_employee_id,
    validated_at=now(),decision_at=case when v_disposition='ON_HOLD' then null else now() end,
    status=case when v_disposition='ON_HOLD' then 'DRAFT' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid()
  where id=p_report_id;
  return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end;
$$;

commit;
