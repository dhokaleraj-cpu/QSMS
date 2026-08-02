-- QSMS Phase 1 unified traceability search
begin;

create or replace view public.v_qsms_trace_events
with (security_invoker = true)
as
select
  p.tenant_id,
  'PART_MASTER'::text as event_type,
  0::integer as stage_no,
  'PART:' || p.id::text as event_key,
  p.id as event_id,
  p.id as part_id,
  p.part_number,
  p.part_name,
  null::text as heat_number,
  null::text as heat_code,
  null::uuid as inward_lot_id,
  null::uuid as batch_id,
  null::uuid as osp_job_id,
  null::uuid as dispatch_id,
  p.part_number as reference,
  p.drawing_number as secondary_reference,
  null::date as event_date,
  p.status,
  null::numeric as quantity,
  customer.party_name as source_name,
  null::text as process_name,
  null::text as result,
  jsonb_strip_nulls(jsonb_build_object(
    'drawing_revision', p.drawing_revision,
    'material_grade', grade.grade_code,
    'manufacturing_route', p.manufacturing_route,
    'finished_weight_kg', p.finished_weight_kg
  )) as detail,
  lower(concat_ws(' ', p.part_number, p.part_name, p.drawing_number, p.drawing_revision, grade.grade_code, customer.party_name, p.manufacturing_route)) as search_text
from public.parts p
left join public.parties customer on customer.id = p.customer_id
left join public.material_grades grade on grade.id = p.material_grade_id

union all

select
  r.tenant_id,
  'RMTC_APPROVAL'::text,
  10,
  'RMTC:' || r.id::text,
  r.id,
  r.part_id,
  p.part_number,
  p.part_name,
  r.heat_number,
  r.heat_code,
  null::uuid,
  null::uuid,
  null::uuid,
  null::uuid,
  r.rmtc_number,
  r.certificate_reference,
  r.certificate_date,
  r.status,
  r.certificate_quantity,
  supplier.party_name,
  'MetLAB RMTC Approval'::text,
  r.chemistry_compliance,
  jsonb_strip_nulls(jsonb_build_object(
    'steel_mill', mill.party_name,
    'material_grade', grade.grade_code,
    'chemistry_results', r.chemistry_results,
    'mechanical_results', r.mechanical_results
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, r.rmtc_number, r.certificate_reference, r.heat_number, r.heat_code, supplier.party_name, mill.party_name, grade.grade_code, r.status, r.chemistry_compliance))
from public.rmtc_approvals r
join public.parts p on p.id = r.part_id
left join public.parties supplier on supplier.id = r.supplier_id
left join public.parties mill on mill.id = r.steel_mill_id
left join public.material_grades grade on grade.id = r.material_grade_id

union all

select
  i.tenant_id,
  'RAW_MATERIAL_INWARD'::text,
  20,
  'INWARD:' || i.id::text,
  i.id,
  i.part_id,
  p.part_number,
  p.part_name,
  i.heat_number,
  i.heat_code,
  i.id,
  null::uuid,
  null::uuid,
  null::uuid,
  i.inward_number,
  i.grn_number,
  i.inward_date,
  i.status,
  i.quantity_received,
  supplier.party_name,
  'Incoming Inspection'::text,
  concat_ws(' / ', i.metallurgical_status, i.dimensional_status),
  jsonb_strip_nulls(jsonb_build_object(
    'invoice_number', i.invoice_number,
    'quantity_accepted', i.quantity_accepted,
    'quantity_rejected', i.quantity_rejected,
    'rmtc_approval_id', i.rmtc_approval_id
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, i.inward_number, i.grn_number, i.invoice_number, i.heat_number, i.heat_code, supplier.party_name, i.status, i.metallurgical_status, i.dimensional_status))
from public.inward_lots i
join public.parts p on p.id = i.part_id
left join public.parties supplier on supplier.id = i.supplier_id

union all

select
  b.tenant_id,
  'PRODUCTION_BATCH'::text,
  30,
  'BATCH:' || b.id::text,
  b.id,
  b.part_id,
  p.part_number,
  p.part_name,
  b.heat_number,
  b.heat_code,
  b.inward_lot_id,
  b.id,
  null::uuid,
  null::uuid,
  b.batch_code,
  b.work_order,
  b.created_at::date,
  b.status,
  b.quantity_available,
  null::text,
  process.process_name,
  null::text,
  jsonb_strip_nulls(jsonb_build_object(
    'quantity_started', b.quantity_started,
    'vendor_batch_number', b.vendor_batch_number,
    'parent_batch_id', b.parent_batch_id
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, b.batch_code, b.work_order, b.heat_number, b.heat_code, b.vendor_batch_number, process.process_name, b.status))
from public.production_batches b
join public.parts p on p.id = b.part_id
left join public.processes process on process.id = b.current_process_id

union all

select
  m.tenant_id,
  'BATCH_MOVEMENT'::text,
  35,
  'MOVE:' || m.id::text,
  m.id,
  b.part_id,
  p.part_number,
  p.part_name,
  b.heat_number,
  b.heat_code,
  b.inward_lot_id,
  b.id,
  null::uuid,
  null::uuid,
  coalesce(m.reference, m.movement_type),
  m.movement_type,
  m.movement_date,
  'RECORDED'::text,
  m.quantity,
  null::text,
  concat_ws(' → ', from_process.process_name, to_process.process_name),
  null::text,
  jsonb_strip_nulls(jsonb_build_object('remarks', m.remarks)),
  lower(concat_ws(' ', p.part_number, p.part_name, b.batch_code, b.heat_number, b.heat_code, m.reference, m.movement_type, from_process.process_name, to_process.process_name, m.remarks))
from public.batch_movements m
join public.production_batches b on b.id = m.batch_id
join public.parts p on p.id = b.part_id
left join public.processes from_process on from_process.id = m.from_process_id
left join public.processes to_process on to_process.id = m.to_process_id

union all

select
  o.tenant_id,
  'OSP_DISPATCH'::text,
  40,
  'OSP-D:' || o.id::text,
  o.id,
  o.part_id,
  p.part_number,
  p.part_name,
  source_batch.heat_number,
  source_batch.heat_code,
  source_batch.inward_lot_id,
  o.osp_batch_id,
  o.id,
  null::uuid,
  o.osp_job_number,
  o.dispatch_challan,
  o.dispatch_date,
  o.status,
  o.quantity_dispatched,
  vendor.party_name,
  process.process_name,
  null::text,
  jsonb_strip_nulls(jsonb_build_object(
    'expected_return_date', o.expected_return_date,
    'process_specification', o.process_specification,
    'required_tests', o.required_tests,
    'source_batch_code', source_batch.batch_code,
    'osp_batch_code', osp_batch.batch_code
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, source_batch.heat_number, source_batch.heat_code, source_batch.batch_code, osp_batch.batch_code, o.osp_job_number, o.dispatch_challan, vendor.party_name, process.process_name, o.process_specification, array_to_string(o.required_tests, ' '), o.status))
from public.osp_jobs o
join public.parts p on p.id = o.part_id
join public.production_batches source_batch on source_batch.id = o.source_batch_id
join public.production_batches osp_batch on osp_batch.id = o.osp_batch_id
left join public.parties vendor on vendor.id = o.vendor_id
left join public.processes process on process.id = o.process_id

union all

select
  o.tenant_id,
  'OSP_RECEIPT'::text,
  50,
  'OSP-R:' || o.id::text,
  o.id,
  o.part_id,
  p.part_number,
  p.part_name,
  source_batch.heat_number,
  source_batch.heat_code,
  source_batch.inward_lot_id,
  o.osp_batch_id,
  o.id,
  null::uuid,
  coalesce(o.vendor_batch_number, o.osp_job_number),
  o.receipt_challan,
  o.receipt_date,
  o.receipt_status,
  o.quantity_received,
  vendor.party_name,
  process.process_name,
  o.inspection_status,
  jsonb_strip_nulls(jsonb_build_object(
    'osp_job_number', o.osp_job_number,
    'quantity_rejected_at_receipt', o.quantity_rejected_at_receipt,
    'receipt_remarks', o.receipt_remarks,
    'osp_status', o.status
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, source_batch.heat_number, source_batch.heat_code, o.osp_job_number, o.receipt_challan, o.vendor_batch_number, vendor.party_name, process.process_name, o.receipt_status, o.inspection_status, o.status))
from public.osp_jobs o
join public.parts p on p.id = o.part_id
join public.production_batches source_batch on source_batch.id = o.source_batch_id
left join public.parties vendor on vendor.id = o.vendor_id
left join public.processes process on process.id = o.process_id
where o.receipt_date is not null or o.quantity_received > 0

union all

select
  inspection.tenant_id,
  'INSPECTION'::text,
  60,
  'INSP:' || inspection.id::text,
  inspection.id,
  inspection.part_id,
  p.part_number,
  p.part_name,
  coalesce(batch.heat_number, inward.heat_number),
  coalesce(batch.heat_code, inward.heat_code),
  coalesce(inspection.inward_lot_id, batch.inward_lot_id),
  inspection.batch_id,
  inspection.osp_job_id,
  null::uuid,
  inspection.report_number,
  inspection.report_type,
  inspection.inspection_date,
  inspection.status,
  inspection.accepted_quantity,
  inspection.inspector,
  inspection.report_type,
  inspection.overall_result,
  jsonb_strip_nulls(jsonb_build_object(
    'sample_size', inspection.sample_size,
    'rejected_quantity', inspection.rejected_quantity,
    'remarks', inspection.remarks
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, batch.batch_code, inward.inward_number, coalesce(batch.heat_number, inward.heat_number), coalesce(batch.heat_code, inward.heat_code), inspection.report_number, inspection.report_type, inspection.inspector, inspection.overall_result, inspection.status, inspection.remarks))
from public.inspection_reports inspection
join public.parts p on p.id = inspection.part_id
left join public.production_batches batch on batch.id = inspection.batch_id
left join public.inward_lots inward on inward.id = inspection.inward_lot_id

union all

select
  test.tenant_id,
  'LAB_TEST'::text,
  70,
  'LAB:' || test.id::text,
  test.id,
  test.part_id,
  p.part_number,
  p.part_name,
  coalesce(batch.heat_number, inward.heat_number),
  coalesce(batch.heat_code, inward.heat_code),
  coalesce(test.inward_lot_id, batch.inward_lot_id),
  test.batch_id,
  test.osp_job_id,
  null::uuid,
  test.report_number,
  test.sample_reference,
  test.test_date,
  test.status,
  null::numeric,
  null::text,
  test.test_type,
  test.overall_result,
  jsonb_strip_nulls(jsonb_build_object(
    'specification_reference', test.specification_reference,
    'results', test.results,
    'remarks', test.remarks
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, batch.batch_code, inward.inward_number, coalesce(batch.heat_number, inward.heat_number), coalesce(batch.heat_code, inward.heat_code), test.report_number, test.sample_reference, test.test_type, test.specification_reference, test.overall_result, test.status, test.results::text, test.remarks))
from public.lab_tests test
join public.parts p on p.id = test.part_id
left join public.production_batches batch on batch.id = test.batch_id
left join public.inward_lots inward on inward.id = test.inward_lot_id

union all

select
  dispatch_line.tenant_id,
  'CUSTOMER_DISPATCH'::text,
  80,
  'DISP:' || dispatch_line.id::text,
  dispatch.id,
  batch.part_id,
  p.part_number,
  p.part_name,
  batch.heat_number,
  batch.heat_code,
  batch.inward_lot_id,
  batch.id,
  null::uuid,
  dispatch.id,
  dispatch.dispatch_number,
  dispatch.invoice_number,
  dispatch.dispatch_date,
  dispatch.status,
  dispatch_line.quantity,
  customer.party_name,
  'Customer Dispatch'::text,
  'RELEASED'::text,
  jsonb_strip_nulls(jsonb_build_object(
    'quality_release_reference', dispatch.quality_release_reference,
    'quality_release_approved_by', dispatch.quality_release_approved_by,
    'destination', dispatch.destination,
    'batch_code', batch.batch_code
  )),
  lower(concat_ws(' ', p.part_number, p.part_name, batch.batch_code, batch.heat_number, batch.heat_code, dispatch.dispatch_number, dispatch.invoice_number, dispatch.quality_release_reference, customer.party_name, dispatch.destination, dispatch.status))
from public.dispatch_batches dispatch_line
join public.dispatches dispatch on dispatch.id = dispatch_line.dispatch_id
join public.production_batches batch on batch.id = dispatch_line.batch_id
join public.parts p on p.id = batch.part_id
left join public.parties customer on customer.id = dispatch.customer_id;

comment on view public.v_qsms_trace_events is
'RLS-respecting unified quality genealogy event stream used by QSMS Phase 1 traceability.';

create or replace function public.qsms_trace_search(p_query text, p_limit integer default 500)
returns setof public.v_qsms_trace_events
language sql
stable
security invoker
set search_path = public
as $$
  with matched as (
    select distinct
      event_type, event_key, event_id, part_id, heat_number, heat_code,
      inward_lot_id, batch_id, osp_job_id, dispatch_id
    from public.v_qsms_trace_events
    where nullif(btrim(p_query), '') is not null
      and search_text ilike '%' || btrim(p_query) || '%'
    limit 200
  )
  select event.*
  from public.v_qsms_trace_events event
  where exists (
    select 1
    from matched anchor
    where event.event_key = anchor.event_key
       or (anchor.dispatch_id is not null and event.dispatch_id = anchor.dispatch_id)
       or (anchor.osp_job_id is not null and event.osp_job_id = anchor.osp_job_id)
       or (anchor.batch_id is not null and event.batch_id = anchor.batch_id)
       or (anchor.inward_lot_id is not null and event.inward_lot_id = anchor.inward_lot_id)
       or (anchor.heat_number is not null and event.part_id = anchor.part_id and event.heat_number = anchor.heat_number)
       or (anchor.heat_code is not null and event.part_id = anchor.part_id and event.heat_code = anchor.heat_code)
       or (event.event_type = 'PART_MASTER' and event.part_id = anchor.part_id)
       or (anchor.event_type = 'PART_MASTER' and event.part_id = anchor.part_id)
  )
  order by event.part_number, event.heat_number nulls first, event.stage_no, event.event_date nulls first, event.reference
  limit greatest(1, least(coalesce(p_limit, 500), 1000));
$$;

revoke all on public.v_qsms_trace_events from anon;
grant select on public.v_qsms_trace_events to authenticated;
revoke all on function public.qsms_trace_search(text, integer) from public, anon;
grant execute on function public.qsms_trace_search(text, integer) to authenticated;

commit;
