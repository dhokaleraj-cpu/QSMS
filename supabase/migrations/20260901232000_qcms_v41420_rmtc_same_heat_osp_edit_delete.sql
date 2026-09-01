-- QCMS v4.14.20 · same-Heat new TC UX + controlled OSP edit/delete RPCs

create or replace function public.qcms_update_osp_material_out(
  p_osp_job_id uuid,
  p_dispatch_date date,
  p_dispatch_challan text,
  p_quantity_dispatched numeric,
  p_expected_return_date date,
  p_remarks text default null
) returns jsonb
language plpgsql security definer set search_path='public','auth'
as $$
declare
  tid uuid:=public.current_tenant_id(); j public.osp_jobs%rowtype; delta numeric; src public.production_batches%rowtype; stock public.supply_opening_stock%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('OSP_TRANSACTIONS','edit') then raise exception 'OSP Transactions Edit permission is required'; end if;
  select * into j from public.osp_jobs where id=p_osp_job_id and tenant_id=tid for update;
  if j.id is null then raise exception 'OSP Material Out record not found'; end if;
  if coalesce(j.quantity_received,0)>0 or j.sample_received_date is not null
     or exists(select 1 from public.inspection_reports r where r.tenant_id=tid and r.osp_job_id=j.id)
     or exists(select 1 from public.lab_tests r where r.tenant_id=tid and r.osp_job_id=j.id)
  then raise exception 'Material Out cannot be edited after Sample/Inspection/OSP Inward activity. Delete or reverse downstream records first.'; end if;
  if coalesce(p_quantity_dispatched,0)<=0 then raise exception 'Material Out quantity must be greater than zero'; end if;
  if nullif(btrim(coalesce(p_dispatch_challan,'')),'') is null then raise exception 'Material Out Challan Number is required'; end if;
  delta:=p_quantity_dispatched-coalesce(j.quantity_dispatched,0);
  select * into src from public.production_batches where id=j.source_batch_id and tenant_id=tid for update;
  if delta>0 and coalesce(src.quantity_available,0)<delta then raise exception 'Additional Material Out quantity exceeds currently available source quantity'; end if;
  if src.id is not null then
    update public.production_batches set quantity_available=greatest(coalesce(quantity_available,0)-delta,0),updated_at=now(),updated_by=auth.uid() where id=src.id;
  end if;
  if j.opening_stock_id is not null then
    select * into stock from public.supply_opening_stock where id=j.opening_stock_id and tenant_id=tid for update;
    if delta>0 and coalesce(stock.available_quantity_pcs,0)<delta then raise exception 'Additional Material Out quantity exceeds Opening Stock balance'; end if;
    update public.supply_opening_stock set available_quantity_pcs=greatest(coalesce(available_quantity_pcs,0)-delta,0),status='ACTIVE',updated_at=now(),updated_by=auth.uid() where id=stock.id;
  end if;
  update public.production_batches set quantity_started=p_quantity_dispatched,updated_at=now(),updated_by=auth.uid() where id=j.osp_batch_id and tenant_id=tid;
  update public.batch_movements set quantity=p_quantity_dispatched,movement_date=p_dispatch_date,remarks=btrim(p_dispatch_challan),updated_at=now(),updated_by=auth.uid()
   where tenant_id=tid and batch_id=j.source_batch_id and movement_type='OSP_DISPATCH' and reference=j.osp_job_number;
  update public.osp_jobs set dispatch_date=p_dispatch_date,dispatch_challan=btrim(p_dispatch_challan),quantity_dispatched=p_quantity_dispatched,
    expected_return_date=p_expected_return_date,dispatch_remarks=nullif(btrim(coalesce(p_remarks,'')),''),updated_at=now(),updated_by=auth.uid()
   where id=j.id returning * into j;
  return to_jsonb(j);
end$$;

create or replace function public.qcms_clear_osp_sample(p_osp_job_id uuid) returns jsonb
language plpgsql security definer set search_path='public','auth'
as $$
declare tid uuid:=public.current_tenant_id(); j public.osp_jobs%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('OSP_TRANSACTIONS','archive') then raise exception 'OSP Transactions Delete/Archive permission is required'; end if;
  select * into j from public.osp_jobs where id=p_osp_job_id and tenant_id=tid for update;
  if j.id is null then raise exception 'OSP transaction not found'; end if;
  if coalesce(j.quantity_received,0)>0 then raise exception 'Sample Receipt cannot be deleted after OSP Inward. Delete inward receipt(s) first.'; end if;
  if exists(select 1 from public.inspection_reports r where r.tenant_id=tid and r.osp_job_id=j.id and r.inspection_scope='OSP_SAMPLE')
     or exists(select 1 from public.lab_tests r where r.tenant_id=tid and r.osp_job_id=j.id and r.inspection_scope='OSP_SAMPLE')
  then raise exception 'Delete linked OSP Sample Dimensional/MetLAB records first'; end if;
  update public.osp_jobs set sample_received_date=null,sample_reference=null,vendor_batch_number=null,sample_gate_status='PENDING',inspection_status='PENDING',updated_at=now(),updated_by=auth.uid()
   where id=j.id returning * into j;
  return to_jsonb(j);
end$$;

create or replace function public.qcms_update_osp_receipt(
  p_receipt_id uuid,
  p_receipt_date date,
  p_receipt_challan text,
  p_vendor_invoice_number text,
  p_vendor_invoice_date date,
  p_tc_number text,
  p_tc_date date,
  p_vendor_batch_number text,
  p_quantity_received numeric,
  p_remarks text default null
) returns jsonb
language plpgsql security definer set search_path='public','auth'
as $$
declare tid uuid:=public.current_tenant_id(); rec public.osp_receipts%rowtype; j public.osp_jobs%rowtype; other_qty numeric; total_qty numeric; latest public.osp_receipts%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not public.qcms_effective_module_permission('OSP_TRANSACTIONS','edit') then raise exception 'OSP Transactions Edit permission is required'; end if;
  select * into rec from public.osp_receipts where id=p_receipt_id and tenant_id=tid for update;
  if rec.id is null then raise exception 'OSP inward receipt not found'; end if;
  select * into j from public.osp_jobs where id=rec.osp_job_id and tenant_id=tid for update;
  if exists(select 1 from public.inspection_reports r where r.tenant_id=tid and r.osp_job_id=j.id and r.inspection_scope='OSP_RECEIPT')
     or exists(select 1 from public.lab_tests r where r.tenant_id=tid and r.osp_job_id=j.id and r.inspection_scope='OSP_RECEIPT')
  then raise exception 'OSP Inward receipt cannot be edited after receipt-level Dimensional/MetLAB inspection. Delete/reopen downstream records first.'; end if;
  if coalesce(p_quantity_received,0)<=0 then raise exception 'Receipt quantity must be greater than zero'; end if;
  select coalesce(sum(quantity_received),0) into other_qty from public.osp_receipts where tenant_id=tid and osp_job_id=j.id and id<>rec.id;
  total_qty:=other_qty+p_quantity_received;
  if total_qty>coalesce(j.quantity_dispatched,0) then raise exception 'Total OSP Inward quantity cannot exceed dispatched quantity'; end if;
  update public.osp_receipts set receipt_date=p_receipt_date,receipt_challan=btrim(p_receipt_challan),vendor_invoice_number=btrim(p_vendor_invoice_number),vendor_invoice_date=p_vendor_invoice_date,
    tc_number=btrim(p_tc_number),tc_date=p_tc_date,vendor_batch_number=btrim(p_vendor_batch_number),quantity_received=p_quantity_received,remarks=nullif(btrim(coalesce(p_remarks,'')),'')
   where id=rec.id returning * into rec;
  update public.batch_movements set quantity=p_quantity_received,movement_date=p_receipt_date,remarks=btrim(p_receipt_challan),updated_at=now(),updated_by=auth.uid()
   where tenant_id=tid and batch_id=j.osp_batch_id and movement_type='OSP_RECEIPT' and reference=rec.receipt_number;
  select * into latest from public.osp_receipts where tenant_id=tid and osp_job_id=j.id order by receipt_date desc, created_at desc limit 1;
  update public.osp_jobs set receipt_number=latest.receipt_number,receipt_date=latest.receipt_date,receipt_challan=latest.receipt_challan,vendor_invoice_number=latest.vendor_invoice_number,
    vendor_invoice_date=latest.vendor_invoice_date,tc_number=latest.tc_number,tc_date=latest.tc_date,vendor_batch_number=latest.vendor_batch_number,
    quantity_received=total_qty,receipt_status=case when total_qty>=quantity_dispatched then 'COMPLETE' else 'PARTIAL' end,
    receipt_quality_disposition='PENDING',inspection_status='PENDING',status='PART_RECEIVED',updated_at=now(),updated_by=auth.uid()
   where id=j.id returning * into j;
  return to_jsonb(j)||jsonb_build_object('updated_receipt',to_jsonb(rec));
end$$;

revoke all on function public.qcms_update_osp_material_out(uuid,date,text,numeric,date,text) from public, anon;
revoke all on function public.qcms_clear_osp_sample(uuid) from public, anon;
revoke all on function public.qcms_update_osp_receipt(uuid,date,text,text,date,text,date,text,numeric,text) from public, anon;
grant execute on function public.qcms_update_osp_material_out(uuid,date,text,numeric,date,text) to authenticated, service_role;
grant execute on function public.qcms_clear_osp_sample(uuid) to authenticated, service_role;
grant execute on function public.qcms_update_osp_receipt(uuid,date,text,text,date,text,date,text,numeric,text) to authenticated, service_role;

insert into public.qcms_release_schema_state(version, build, applied_at, details)
values('4.14.20','41420-RMTC-SAME-HEAT-OSP-EDIT-DELETE',now(),jsonb_build_object('status','READY'))
on conflict (version) do update set build=excluded.build, applied_at=excluded.applied_at, details=excluded.details;
