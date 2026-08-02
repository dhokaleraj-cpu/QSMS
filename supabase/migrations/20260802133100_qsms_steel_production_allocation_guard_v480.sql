-- QSMS 4.8.0 allocation correction: batch quantities are pieces, not kilograms.
begin;
create or replace function public.enforce_inward_rmtc_link()
returns trigger language plpgsql security definer set search_path=public,auth as $$
declare cert public.rmtc_approvals%rowtype;part_decision public.rmtc_part_approvals%rowtype;source_detail public.part_raw_material_details%rowtype;already_received numeric;allocated_to_batches numeric;steel_qty numeric;production_qty numeric;input_weight numeric;required_steel numeric;
begin
  select * into cert from public.rmtc_approvals where id=new.rmtc_approval_id;
  if cert.id is null then raise exception 'Linked RMTC approval does not exist'; end if;
  if cert.tenant_id<>new.tenant_id then raise exception 'RMTC and inward tenant mismatch'; end if;
  if cert.status not in ('APPROVED','PARTIALLY_APPROVED') or cert.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then raise exception 'Material inward is allowed only against an Accepted or Accepted Under Reserve RMTC'; end if;
  if new.rmtc_part_approval_id is null then select * into part_decision from public.rmtc_part_approvals where rmtc_approval_id=cert.id and part_id=coalesce(new.part_id,cert.part_id) limit 1;else select * into part_decision from public.rmtc_part_approvals where id=new.rmtc_part_approval_id and rmtc_approval_id=cert.id;end if;
  if part_decision.id is null then raise exception 'Select a covered RMTC Part Number'; end if;
  if part_decision.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then raise exception 'The selected RMTC Part Number is not accepted for inward'; end if;
  if new.supplier_source_detail_id is not null then select * into source_detail from public.part_raw_material_details where id=new.supplier_source_detail_id and tenant_id=new.tenant_id and part_id=part_decision.part_id and supplier_id=cert.supplier_id and status='ACTIVE';end if;
  if source_detail.id is null then select * into source_detail from public.part_raw_material_details where tenant_id=new.tenant_id and part_id=part_decision.part_id and supplier_id=cert.supplier_id and status='ACTIVE' order by case when id=cert.selected_source_detail_id then 0 else 1 end,sequence_no,created_at limit 1;end if;
  if source_detail.id is null then raise exception 'Active supplier forging parameters are required in Part Master'; end if;
  steel_qty:=coalesce(new.steel_quantity_kg,new.quantity_received,0);production_qty:=coalesce(new.production_quantity_pcs,0);input_weight:=coalesce(new.input_weight_kg,source_detail.input_weight_kg,source_detail.gross_weight_kg,source_detail.forging_weight_kg,0);required_steel:=round(production_qty*input_weight,3);
  if steel_qty<=0 then raise exception 'Steel Quantity (kg) must be greater than zero'; end if;
  if production_qty<=0 then raise exception 'Part Production Quantity must be greater than zero'; end if;
  if input_weight<=0 then raise exception 'Input Weight (kg/part) is required in Part Master supplier forging parameters'; end if;
  if required_steel>steel_qty then raise exception 'Required production steel quantity % kg exceeds inward steel quantity % kg',required_steel,steel_qty;end if;
  new.rmtc_part_approval_id:=part_decision.id;new.part_id:=part_decision.part_id;new.supplier_id:=cert.supplier_id;new.heat_number:=cert.heat_number;new.heat_code:=cert.heat_code;new.rmtc_disposition:=part_decision.disposition;new.supplier_source_detail_id:=source_detail.id;new.input_weight_kg:=input_weight;new.production_quantity_pcs:=production_qty;new.required_steel_quantity_kg:=required_steel;new.steel_quantity_kg:=steel_qty;new.quantity_received:=steel_qty;
  select coalesce(sum(coalesce(steel_quantity_kg,quantity_received)),0) into already_received from public.inward_lots where rmtc_approval_id=cert.id and (new.id is null or id<>new.id);
  if already_received+steel_qty>cert.certificate_quantity then raise exception 'Material inward steel quantity exceeds the available RMTC steel balance'; end if;
  select coalesce(sum(quantity_started),0) into allocated_to_batches from public.production_batches where inward_lot_id=new.id and parent_batch_id is null;
  if allocated_to_batches>production_qty then raise exception 'Part Production Quantity cannot be reduced below % pieces already allocated to production batches',allocated_to_batches; end if;
  if new.receipt_disposition='REJECTED' then new.quantity_accepted:=0;new.quantity_rejected:=steel_qty;new.status:='REJECTED';elsif new.receipt_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then if nullif(btrim(coalesce(new.reserve_reason,'')),'') is null then raise exception 'Reason is mandatory for On Hold or Accepted Under Reserve inward';end if;new.status:='HOLD_PENDING_INSPECTION';elsif new.receipt_disposition='ACCEPTED' then new.quantity_accepted:=case when new.quantity_accepted=0 then steel_qty-new.quantity_rejected else new.quantity_accepted end;new.status:=case when new.metallurgical_status in ('PASS','NOT_REQUIRED') and new.dimensional_status in ('PASS','NOT_REQUIRED') then 'RELEASED' else 'HOLD_PENDING_INSPECTION' end;else new.status:='HOLD_PENDING_INSPECTION';end if;
  return new;
end;$$;
commit;
