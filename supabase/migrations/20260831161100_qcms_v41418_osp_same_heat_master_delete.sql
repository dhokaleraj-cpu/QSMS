-- QCMS v4.14.18 / 2 of 3 — OSP controlled delete, same-Heat identity, password master deletion.
-- Additive/backward-compatible. No transactional/business rows are reset.

begin;

-- -----------------------------------------------------------------------------
-- 6B) Same Heat Number / Heat Code identity and controlled OSP transaction delete.
-- -----------------------------------------------------------------------------
-- Existing Heat Numbers may have multiple QCMS/Supplier RMTC certificate records,
-- but they must remain one genealogy identity. Any new RMTC for an existing Heat
-- automatically reuses the established Internal Heat Code instead of creating a
-- second Heat Code for the same Heat Number.
create or replace function public.qcms_enforce_same_heat_code()
returns trigger
language plpgsql
set search_path='public','auth' as $$
declare
  canonical_code text;
begin
  new.normalized_heat_number:=public.qsms_normalize_heat_number(new.heat_number);
  if new.normalized_heat_number='' then return new; end if;
  select nullif(btrim(r.heat_code),'') into canonical_code
  from public.rmtc_approvals r
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number
    and r.id<>new.id
    and nullif(btrim(coalesce(r.heat_code,'')),'') is not null
  order by r.created_at,r.id
  limit 1;
  if canonical_code is not null then
    new.heat_code:=canonical_code;
  end if;
  return new;
end $$;

drop trigger if exists trg_qcms_same_heat_code on public.rmtc_approvals;
create trigger trg_qcms_same_heat_code
before insert or update of heat_number,heat_code on public.rmtc_approvals
for each row execute function public.qcms_enforce_same_heat_code();

-- Delete one partial OSP inward receipt and recalculate the parent OSP job. This
-- is intentionally blocked once receipt-level quality reports exist because those
-- reports would otherwise refer to a quantity that no longer exists.
create or replace function public.qcms_delete_osp_receipt(p_receipt_id uuid)
returns jsonb
language plpgsql security definer set search_path='public','auth' as $$
declare
  tid uuid:=public.current_tenant_id();
  receipt_row public.osp_receipts%rowtype;
  job_row public.osp_jobs%rowtype;
  latest_receipt public.osp_receipts%rowtype;
  new_total numeric:=0;
  remaining_count integer:=0;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('OSP_TRANSACTIONS','archive') then
    raise exception 'OSP Transactions Delete/Archive permission is required';
  end if;
  select * into receipt_row from public.osp_receipts where id=p_receipt_id and tenant_id=tid for update;
  if receipt_row.id is null then raise exception 'OSP receipt was not found'; end if;
  select * into job_row from public.osp_jobs where id=receipt_row.osp_job_id and tenant_id=tid for update;
  if job_row.id is null then raise exception 'Parent OSP transaction was not found'; end if;
  if job_row.production_released_at is not null or job_row.status='COMPLETED' then
    raise exception 'This OSP receipt is already released to production and cannot be deleted';
  end if;
  if exists(select 1 from public.lab_tests where tenant_id=tid and osp_job_id=job_row.id and inspection_scope='OSP_RECEIPT')
     or exists(select 1 from public.inspection_reports where tenant_id=tid and osp_job_id=job_row.id and inspection_scope='OSP_RECEIPT') then
    raise exception 'Delete the OSP receipt inspection report(s) first before deleting this receipt';
  end if;

  delete from public.batch_movements
   where tenant_id=tid and batch_id=job_row.osp_batch_id
     and movement_type='OSP_RECEIPT' and reference=receipt_row.receipt_number;
  delete from public.osp_receipts where id=receipt_row.id and tenant_id=tid;

  select coalesce(sum(r.quantity_received),0),count(*) into new_total,remaining_count
  from public.osp_receipts r where r.tenant_id=tid and r.osp_job_id=job_row.id;
  select * into latest_receipt from public.osp_receipts r
  where r.tenant_id=tid and r.osp_job_id=job_row.id
  order by r.created_at desc,r.id desc limit 1;

  update public.osp_jobs set
    receipt_number=case when remaining_count>0 then latest_receipt.receipt_number else null end,
    receipt_date=case when remaining_count>0 then latest_receipt.receipt_date else null end,
    receipt_challan=case when remaining_count>0 then latest_receipt.receipt_challan else null end,
    vendor_invoice_number=case when remaining_count>0 then latest_receipt.vendor_invoice_number else null end,
    vendor_invoice_date=case when remaining_count>0 then latest_receipt.vendor_invoice_date else null end,
    tc_number=case when remaining_count>0 then latest_receipt.tc_number else null end,
    tc_date=case when remaining_count>0 then latest_receipt.tc_date else null end,
    vendor_batch_number=coalesce(case when remaining_count>0 then latest_receipt.vendor_batch_number else null end,vendor_batch_number),
    quantity_received=new_total,
    receipt_status=case when new_total<=0 then 'PENDING' when new_total>=quantity_dispatched then 'COMPLETE' else 'PARTIAL' end,
    receipt_quality_disposition='PENDING',
    inspection_status='PENDING',
    status=case when new_total<=0 then 'AT_VENDOR' else 'PART_RECEIVED' end,
    production_released_at=null,
    updated_at=now(),updated_by=auth.uid()
  where id=job_row.id;
  update public.production_batches set
    quantity_available=0,
    status=case when new_total<=0 then 'AT_OSP' else 'HOLD_PENDING_OSP_INSPECTION' end,
    updated_at=now(),updated_by=auth.uid()
  where id=job_row.osp_batch_id and tenant_id=tid;
  return jsonb_build_object('deleted',true,'receipt_id',p_receipt_id,'osp_job_id',job_row.id,'quantity_received',new_total);
end $$;
revoke all on function public.qcms_delete_osp_receipt(uuid) from public,anon;
grant execute on function public.qcms_delete_osp_receipt(uuid) to authenticated;

-- Delete an entire OSP transaction only when no quality report/downstream genealogy
-- exists. The function reverses the Material Out allocation before removing the
-- OSP child batch, so deleting an early erroneous transaction never loses stock.
create or replace function public.qcms_delete_osp_transaction(p_osp_job_id uuid)
returns jsonb
language plpgsql security definer set search_path='public','auth' as $$
declare
  tid uuid:=public.current_tenant_id();
  job_row public.osp_jobs%rowtype;
  source_row public.production_batches%rowtype;
  stock_row public.supply_opening_stock%rowtype;
  other_allocated numeric:=0;
  restored_open numeric:=0;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('OSP_TRANSACTIONS','archive') then
    raise exception 'OSP Transactions Delete/Archive permission is required';
  end if;
  select * into job_row from public.osp_jobs where id=p_osp_job_id and tenant_id=tid for update;
  if job_row.id is null then raise exception 'OSP transaction was not found'; end if;

  if job_row.production_released_at is not null or job_row.status='COMPLETED' then
    raise exception 'This OSP transaction is already released to production and cannot be deleted';
  end if;
  if exists(select 1 from public.lab_tests where tenant_id=tid and osp_job_id=job_row.id)
     or exists(select 1 from public.inspection_reports where tenant_id=tid and osp_job_id=job_row.id) then
    raise exception 'Delete linked OSP MetLAB / Dimensional report(s) first';
  end if;
  if exists(select 1 from public.production_batches where tenant_id=tid and parent_batch_id=job_row.osp_batch_id)
     or exists(select 1 from public.dispatch_batches where tenant_id=tid and batch_id=job_row.osp_batch_id)
     or exists(select 1 from public.customer_report_packages where tenant_id=tid and batch_id=job_row.osp_batch_id) then
    raise exception 'This OSP transaction has downstream production/dispatch genealogy and cannot be deleted';
  end if;

  select * into source_row from public.production_batches where id=job_row.source_batch_id and tenant_id=tid for update;

  if job_row.opening_stock_id is not null then
    select * into stock_row from public.supply_opening_stock where id=job_row.opening_stock_id and tenant_id=tid for update;
    if stock_row.id is not null then
      restored_open:=least(coalesce(stock_row.quantity_pcs,0),coalesce(stock_row.available_quantity_pcs,0)+coalesce(job_row.quantity_dispatched,0));
      update public.supply_opening_stock set
        available_quantity_pcs=restored_open,
        status=case when restored_open>0 then 'ACTIVE' else status end,
        stage=case when stage='AT_OSP' and restored_open>0 then 'OSP_READY' else stage end,
        updated_at=now(),updated_by=auth.uid()
      where id=stock_row.id;
      if source_row.id is not null then
        update public.production_batches set quantity_available=restored_open,updated_at=now(),updated_by=auth.uid()
        where id=source_row.id;
      end if;
    end if;
  elsif job_row.source_inward_lot_id is not null and source_row.id is not null then
    select coalesce(sum(o.quantity_dispatched),0) into other_allocated
    from public.osp_jobs o
    where o.tenant_id=tid and o.source_inward_lot_id=job_row.source_inward_lot_id
      and o.id<>job_row.id and o.status<>'CANCELLED';
    update public.production_batches set
      quantity_available=greatest(coalesce(quantity_started,0)-other_allocated,0),
      updated_at=now(),updated_by=auth.uid()
    where id=source_row.id;
  end if;

  delete from public.batch_movements
   where tenant_id=tid and batch_id=job_row.source_batch_id
     and movement_type='OSP_DISPATCH' and reference=job_row.osp_job_number;
  -- OSP receipt rows cascade from the job; their batch movements cascade when the
  -- OSP child production batch is removed below.
  delete from public.osp_jobs where id=job_row.id and tenant_id=tid;
  delete from public.production_batches where id=job_row.osp_batch_id and tenant_id=tid;

  return jsonb_build_object('deleted',true,'osp_job_id',job_row.id,'osp_job_number',job_row.osp_job_number,'restored_quantity',job_row.quantity_dispatched);
end $$;
revoke all on function public.qcms_delete_osp_transaction(uuid) from public,anon;
grant execute on function public.qcms_delete_osp_transaction(uuid) to authenticated;

-- -----------------------------------------------------------------------------
-- 7) Password-protected delete RPC: expand master coverage and use the same
--    effective Delete/Archive permission model as the UI.
-- -----------------------------------------------------------------------------
create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare
 tid uuid:=public.current_tenant_id();
 module_name text:=public.qsms_module_for_table(p_table_name);
 deleted_count integer:=0;
 allowed_tables constant text[]:=array[
  'company_branches','parts','part_material_grade_links','part_raw_material_details','part_raw_material_technical_data','part_supplier_price_history',
  'part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements',
  'material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards',
  'inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments',
  'rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions',
  'inward_lots','inspection_reports','inspection_results','lab_tests','production_batches','batch_movements',
  'npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points',
  'ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items',
  'control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings',
  'msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics','qc_calculation_records'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 if p_table_name is null or not (p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table'; end if;
 if not public.qcms_effective_module_permission(module_name,'archive') then raise exception 'Delete/Archive permission is not assigned for this module'; end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
 get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant'; end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then
 raise exception 'This record is linked to another master or transaction. Delete the linked child record first, or deactivate the master instead.';
end $$;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
