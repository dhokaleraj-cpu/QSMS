-- QCMS v4.13.4
-- Approved RMTCs may be reused for repeated Material Inward / production allocations
-- against any already-approved covered part until the global RMTC steel quantity is consumed.
-- The original worksheet planned-production quantity is informational and is no longer a hard inward cap.
begin;

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

  -- Global RMTC certificate quantity is the only cumulative consumption ceiling.
  select coalesce(sum(coalesce(required_steel_quantity_kg,steel_quantity_kg,quantity_received,0)),0) into heat_allocated_steel
  from public.inward_lots where rmtc_approval_id=cert.id and (new.id is null or id<>new.id);
  if heat_allocated_steel+required_steel>cert.certificate_quantity then
    raise exception 'Cumulative heat production steel % kg exceeds RMTC steel quantity % kg',round(heat_allocated_steel+required_steel,3),cert.certificate_quantity;
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

comment on function public.enforce_inward_rmtc_link() is
'QCMS v4.13.4: approved RMTCs are reusable across already-approved covered parts until global RMTC steel balance is consumed; part worksheet planned quantity is informational.';

commit;
