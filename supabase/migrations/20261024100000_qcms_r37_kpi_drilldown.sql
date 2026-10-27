-- QCMS v4.14.49 R37 · KPI drill-down, card keys and module infographic cards.
-- Idempotent and additive: create or replace function only. Every function is SECURITY INVOKER,
-- so the base-table RLS (tenant isolation) decides what each user sees.
--
--  1. public.qcms_kpi_num(numeric)            - number -> short text (detail column helper)
--  2. public.qcms_kpi_card_k(key, label, ...) - card json with a stable "key" and "route"
--  3. public.qcms_kpi_dashboard(text)         - same output shape, every card now carries key + route
--  4. public.qcms_kpi_base(text)              - the records behind a card key (no joins, no limit)
--  5. public.qcms_kpi_records(text,text,int)  - drill-down grid rows (part / party labels, limit)
--  6. public.qcms_kpi_spark(text,text)        - 6-month record counts for module sparklines
--  7. public.qcms_module_card(...)            - module card json builder (progress + tone)
--  8. public.qcms_module_cards(text)          - one infographic card per module of a department

-- 1 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_num(p_value numeric)
returns text language sql immutable set search_path = public as $$
  select rtrim(rtrim(to_char(round(coalesce(p_value, 0), 2), 'FM999,999,999,990.00'), '0'), '.')
$$;

-- 2 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_card_k(p_key text, p_label text, p_value numeric, p_unit text, p_tone text, p_route text)
returns jsonb language sql immutable set search_path = public as $$
  select jsonb_build_object('key', p_key, 'label', p_label, 'value', coalesce(p_value, 0), 'unit', coalesce(p_unit, ''),
                            'tone', coalesce(p_tone, 'neutral'), 'route', p_route, 'web_route', p_route)
$$;

-- 3 --------------------------------------------------------------------------------------------
-- The R35 dashboard keeps its exact calculations; every qcms_kpi_card('<label>', ...) call is rewritten
-- to qcms_kpi_card_k('<key>', '<label>', ...). Re-running is a no-op (the patterns no longer match).
do $do$
declare
  v_def text;
  v_new text;
  m record;
begin
  if to_regprocedure('public.qcms_kpi_dashboard(text)') is null then
    return;
  end if;
  v_def := pg_get_functiondef('public.qcms_kpi_dashboard(text)'::regprocedure);
  v_new := v_def;
  for m in select * from (values
      ('Inward on quality hold', 'inward_hold'), ('MetLAB pending', 'metlab_pending'), ('Bend Test pending', 'bend_pending'),
      ('Dimensional pending', 'dimensional_pending'), ('Reports finalized this month', 'reports_final_month'),
      ('Rejection (180 days)', 'rejection_180d'), ('RMTC pending', 'rmtc_pending'), ('Complaints open', 'complaints_open'),
      ('Calibration overdue', 'calibration_overdue'), ('Calibration due ≤ 30 days', 'calibration_due_30'),
      ('Open customer orders', 'customer_orders_open'), ('Open order quantity', 'customer_order_qty_open'),
      ('PO pending approval', 'po_pending_approval'), ('Open purchase orders', 'po_open'), ('RM on order', 'rm_on_order'),
      ('RM received this month', 'rm_received_month'), ('Forging orders open', 'forging_orders_open'),
      ('Dispatched this month', 'dispatched_month'), ('Pieces available in batches', 'batch_pcs_available'),
      ('Active production batches', 'batches_active'), ('OSP at vendor', 'osp_at_vendor'), ('OSP sample pending', 'osp_sample_pending'),
      ('OSP receipt quality pending', 'osp_receipt_pending'), ('Machined this month', 'machined_month'),
      ('Finished goods this month', 'fg_month'), ('NPD open', 'npd_open'), ('NPD in progress', 'npd_in_progress'), ('NPD late', 'npd_late'),
      ('APQP / PPAP active', 'apqp_active'), ('APQP average completion', 'apqp_completion'), ('NPD steps open', 'npd_steps_open'),
      ('NPD steps overdue', 'npd_steps_overdue'), ('First-pass yield (final reports)', 'fpy_final_reports'),
      ('Open PO value', 'po_open_value'), ('Heats released this month', 'heats_released_month')
    ) as t(label, card_key)
  loop
    v_new := replace(v_new, format('public.qcms_kpi_card(%L, ', m.label), format('public.qcms_kpi_card_k(%L, %L, ', m.card_key, m.label));
  end loop;
  if v_new <> v_def then
    execute v_new;
  end if;
end
$do$;

-- 4 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_base(p_card_key text)
returns table(source_table text, record_id uuid, reference text, part_id uuid, party_id uuid, status text,
              record_date date, detail text, sort_ts timestamptz)
language plpgsql stable security invoker set search_path = public as $$
#variable_conflict use_column
declare
  k text := lower(trim(coalesce(p_card_key, '')));
  v_month date := date_trunc('month', current_date)::date;
  v_tab regclass;
begin
  -- ---------------------------------------------------------------- Quality
  if k in ('inward_hold', 'mod_inward') then
    return query select 'inward_lots'::text, l.id, coalesce(l.inward_number, l.grn_number), l.part_id, l.supplier_id, l.status, l.inward_date,
      concat_ws(' · ', 'Heat ' || l.heat_number, public.qcms_kpi_num(l.steel_quantity_kg) || ' kg', 'MetLAB ' || l.metallurgical_status, 'Dim ' || l.dimensional_status), l.created_at
      from public.inward_lots l where l.status = 'HOLD_PENDING_INSPECTION';
  elsif k = 'inward_released' then
    return query select 'inward_lots'::text, l.id, coalesce(l.inward_number, l.grn_number), l.part_id, l.supplier_id, l.status, l.inward_date,
      concat_ws(' · ', 'Heat ' || l.heat_number, public.qcms_kpi_num(l.steel_quantity_kg) || ' kg'), l.created_at
      from public.inward_lots l where l.status = 'RELEASED';
  elsif k = 'heats_released_month' then
    return query select 'inward_lots'::text, l.id, coalesce(l.inward_number, l.grn_number), l.part_id, l.supplier_id, l.status, l.inward_date,
      concat_ws(' · ', 'Heat ' || l.heat_number, 'released ' || to_char(coalesce(l.released_at, l.updated_at), 'DD-Mon-YYYY')), coalesce(l.released_at, l.updated_at)
      from public.inward_lots l where l.status = 'RELEASED' and coalesce(l.released_at, l.updated_at) >= v_month;
  elsif k = 'inward_all' then
    return query select 'inward_lots'::text, l.id, coalesce(l.inward_number, l.grn_number), l.part_id, l.supplier_id, l.status, l.inward_date,
      concat_ws(' · ', 'Heat ' || l.heat_number, public.qcms_kpi_num(l.steel_quantity_kg) || ' kg', public.qcms_kpi_num(l.production_quantity_pcs) || ' pcs'), l.created_at
      from public.inward_lots l;
  elsif k in ('inward_accepted_pcs', 'inward_rejected_pcs', 'inward_hold_pcs') then
    return query select 'inward_lots'::text, l.id, coalesce(l.inward_number, l.grn_number), l.part_id, l.supplier_id, l.status, l.inward_date,
      concat_ws(' · ', 'Heat ' || l.heat_number, 'accepted ' || public.qcms_kpi_num(l.accepted_production_quantity_pcs), 'rejected ' || public.qcms_kpi_num(l.rejected_production_quantity_pcs),
                'on hold ' || public.qcms_kpi_num(l.hold_production_quantity_pcs)), l.created_at
      from public.inward_lots l
     where (k = 'inward_accepted_pcs' and coalesce(l.accepted_production_quantity_pcs, 0) <> 0)
        or (k = 'inward_rejected_pcs' and coalesce(l.rejected_production_quantity_pcs, 0) <> 0)
        or (k = 'inward_hold_pcs' and coalesce(l.hold_production_quantity_pcs, 0) <> 0);
  elsif k = 'rejection_180d' then
    return query select 'inward_lots'::text, l.id, coalesce(l.inward_number, l.grn_number), l.part_id, l.supplier_id, l.status, l.inward_date,
      concat_ws(' · ', 'Heat ' || l.heat_number, 'rejected ' || public.qcms_kpi_num(l.rejected_production_quantity_pcs) || ' of '
                || public.qcms_kpi_num(coalesce(l.accepted_production_quantity_pcs, 0) + coalesce(l.rejected_production_quantity_pcs, 0)) || ' pcs'),
      -- sort lots with rejections first
      case when coalesce(l.rejected_production_quantity_pcs, 0) > 0 then now() + make_interval(secs => l.rejected_production_quantity_pcs::double precision) else l.created_at end
      from public.inward_lots l where l.created_at >= current_date - 180;
  elsif k in ('metlab_pending', 'bend_pending', 'mod_metlab', 'mod_osp_metlab', 'mod_bend') then
    return query select 'lab_tests'::text, t.id, t.report_number, t.part_id, coalesce(t.supplier_id, t.osp_vendor_id, t.customer_id), t.status, t.test_date,
      concat_ws(' · ', case when coalesce(t.results->>'inspection_method', '') = 'BEND_TEST' then 'Bend Test' when t.osp_job_id is not null then 'OSP MetLAB' else 'MetLAB' end,
                'Heat ' || t.heat_number, nullif(t.layout_name_snapshot, ''), 'Decision ' || t.disposition), t.created_at
      from public.lab_tests t
     where t.status <> 'FINAL'
       and case k when 'bend_pending' then coalesce(t.results->>'inspection_method', '') = 'BEND_TEST'
                  when 'mod_bend' then coalesce(t.results->>'inspection_method', '') = 'BEND_TEST'
                  when 'metlab_pending' then coalesce(t.results->>'inspection_method', '') <> 'BEND_TEST'
                  when 'mod_metlab' then coalesce(t.results->>'inspection_method', '') <> 'BEND_TEST' and t.osp_job_id is null
                  else coalesce(t.results->>'inspection_method', '') <> 'BEND_TEST' and t.osp_job_id is not null end;
  elsif k in ('dimensional_pending', 'mod_dimensional', 'mod_osp_dimensional') then
    return query select 'inspection_reports'::text, r.id, r.report_number, r.part_id, r.supplier_id, r.status, r.inspection_date,
      concat_ws(' · ', initcap(replace(coalesce(r.inspection_scope, r.report_type), '_', ' ')), 'Heat ' || r.heat_number, nullif(r.layout_name_snapshot, '')), r.created_at
      from public.inspection_reports r
     where r.status <> 'FINAL'
       and case k when 'mod_dimensional' then r.osp_job_id is null when 'mod_osp_dimensional' then r.osp_job_id is not null else true end;
  elsif k in ('reports_final_month', 'fpy_final_reports', 'mod_quality_reports') then
    return query
      select 'lab_tests'::text, t.id, t.report_number, t.part_id, coalesce(t.supplier_id, t.osp_vendor_id, t.customer_id), t.status, t.test_date,
        concat_ws(' · ', case when coalesce(t.results->>'inspection_method', '') = 'BEND_TEST' then 'Bend Test' else 'MetLAB' end,
                  'Decision ' || coalesce(t.disposition, 'PENDING'), 'Heat ' || t.heat_number), coalesce(t.decision_at, t.updated_at)
        from public.lab_tests t
       where (k = 'reports_final_month' and t.status = 'FINAL' and coalesce(t.decision_at, t.updated_at) >= v_month)
          or (k = 'fpy_final_reports' and t.status = 'FINAL')
          or (k = 'mod_quality_reports' and t.status <> 'FINAL')
      union all
      select 'inspection_reports'::text, r.id, r.report_number, r.part_id, r.supplier_id, r.status, r.inspection_date,
        concat_ws(' · ', 'Dimensional', 'Decision ' || coalesce(r.disposition, 'PENDING'), 'Heat ' || r.heat_number), coalesce(r.decision_at, r.updated_at)
        from public.inspection_reports r
       where (k = 'reports_final_month' and r.status = 'FINAL' and coalesce(r.decision_at, r.updated_at) >= v_month)
          or (k = 'fpy_final_reports' and r.status = 'FINAL')
          or (k = 'mod_quality_reports' and r.status <> 'FINAL');
  elsif k in ('rmtc_pending', 'mod_rmtc', 'rmtc_draft', 'rmtc_approval_pending', 'rmtc_accepted', 'rmtc_under_reserve', 'rmtc_all') then
    return query select 'rmtc_approvals'::text, a.id, coalesce(a.rmtc_number, a.certificate_reference), a.part_id, a.supplier_id, a.status, coalesce(a.certificate_date, a.entry_date),
      concat_ws(' · ', 'Heat ' || a.heat_number, public.qcms_kpi_num(a.certificate_quantity) || ' kg', 'Validation ' || a.validation_result, 'Decision ' || a.disposition), a.created_at
      from public.rmtc_approvals a
     where case k when 'rmtc_draft' then a.status = 'DRAFT'
                  when 'rmtc_approval_pending' then a.status = 'APPROVAL_PENDING'
                  when 'rmtc_accepted' then a.disposition = 'ACCEPTED'
                  when 'rmtc_under_reserve' then a.disposition = 'ACCEPTED_UNDER_RESERVE'
                  when 'rmtc_all' then true
                  else coalesce(a.status, '') not in ('APPROVED', 'REJECTED', 'CANCELLED') end;
  elsif k in ('complaints_open', 'mod_customer_complaints', 'mod_supplier_complaints') then
    return query select 'quality_complaints'::text, c.id, c.complaint_number, c.part_id, c.party_id, c.status, c.complaint_date,
      concat_ws(' · ', initcap(c.complaint_type), left(c.subject, 80), 'target ' || to_char(c.target_closure_date, 'DD-Mon-YYYY'), initcap(c.severity)), c.created_at
      from public.quality_complaints c
     where coalesce(c.status, '') not in ('CLOSED', 'CANCELLED')
       and case k when 'mod_customer_complaints' then c.complaint_type = 'CUSTOMER' when 'mod_supplier_complaints' then c.complaint_type = 'SUPPLIER' else true end;
  elsif k = 'mod_capa' then
    return query select 'quality_complaint_actions'::text, x.id, coalesce(c.complaint_number, '') || ' / A' || coalesce(x.action_no::text, ''), c.part_id, c.party_id, x.status, x.target_date,
      concat_ws(' · ', initcap(replace(x.action_type, '_', ' ')), left(x.action_description, 90)), x.created_at
      from public.quality_complaint_actions x left join public.quality_complaints c on c.id = x.complaint_id
     where coalesce(x.status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED');
  elsif k in ('calibration_overdue', 'calibration_due_30', 'mod_calibration') then
    return query select 'quality_assets'::text, q.id, coalesce(q.asset_code, q.asset_number), null::uuid, null::uuid, q.status, least(q.next_due_date, q.next_validation_due_date),
      concat_ws(' · ', q.asset_name, q.asset_type, q.location, 'calibration due ' || to_char(q.next_due_date, 'DD-Mon-YYYY'), 'validation due ' || to_char(q.next_validation_due_date, 'DD-Mon-YYYY')),
      least(q.next_due_date, q.next_validation_due_date)::timestamptz
      from public.quality_assets q
     where coalesce(q.status, 'ACTIVE') = 'ACTIVE'
       and case k when 'calibration_overdue' then least(q.next_due_date, q.next_validation_due_date) < current_date
                  when 'calibration_due_30' then least(q.next_due_date, q.next_validation_due_date) between current_date and current_date + 30
                  else least(q.next_due_date, q.next_validation_due_date) <= current_date + 30 end;
  elsif k = 'mod_standard_room' then
    return query select 'standard_room_inspection_records'::text, s.id, coalesce(s.report_number, s.batch_code), s.part_id, null::uuid, s.inspection_status, s.inspection_date,
      concat_ws(' · ', s.instrument_type, 'Heat ' || s.heat_number, 'Batch ' || s.batch_code), s.created_at
      from public.standard_room_inspection_records s where coalesce(s.inspection_status, '') in ('PENDING', 'HOLD');
  elsif k = 'mod_layouts' then
    return query select 'inspection_plans'::text, p.id, coalesce(p.plan_number, p.layout_name), p.part_id, null::uuid, p.status, coalesce(p.effective_date, p.created_at::date),
      concat_ws(' · ', p.layout_name, initcap(replace(p.layout_type, '_', ' ')), 'Rev ' || p.revision), p.created_at
      from public.inspection_plans p where coalesce(p.status, '') in ('DRAFT', 'APPROVAL_PENDING');
  -- ---------------------------------------------------------------- Supply chain
  elsif k in ('customer_orders_open', 'customer_order_qty_open', 'mod_customer_orders', 'mod_customer_orders_overdue') then
    return query select 'supply_customer_orders'::text, o.id, concat_ws(' / ', coalesce(o.customer_order_no, o.master_reference_no), o.order_position), o.part_id, o.customer_id, o.status,
      coalesce(o.customer_delivery_date, o.schedule_month),
      concat_ws(' · ', public.qcms_kpi_num(o.order_qty_pcs) || ' pcs', 'schedule ' || to_char(o.schedule_month, 'Mon YYYY'), initcap(replace(o.supply_flow, '_', ' '))), o.created_at
      from public.supply_customer_orders o
     where o.status in ('OPEN', 'IN_PROGRESS')
       and (k <> 'mod_customer_orders_overdue' or o.customer_delivery_date < current_date);
  elsif k in ('po_pending_approval', 'mod_po_approval', 'po_open', 'po_open_value', 'mod_po_open') then
    return query select 'supply_purchase_orders'::text, o.id, o.po_number, null::uuid, o.supplier_id, o.status, o.order_date,
      concat_ws(' · ', initcap(replace(o.po_type, '_', ' ')), coalesce(o.currency, 'INR') || ' ' || public.qcms_kpi_num(o.grand_total),
                'delivery ' || to_char(o.delivery_date, 'DD-Mon-YYYY'), 'approval ' || lower(replace(o.approval_status, '_', ' '))), coalesce(o.submitted_at, o.created_at)
      from public.supply_purchase_orders o
     where case when k in ('po_pending_approval', 'mod_po_approval') then o.approval_status = 'PENDING_APPROVAL' else o.status in ('OPEN', 'PARTIAL') end;
  elsif k = 'mod_po_confirmation' then
    return query select 'supply_po_confirmations'::text, f.id, coalesce(o.po_number, f.confirmation_reference), null::uuid, coalesce(f.supplier_id, o.supplier_id), f.confirmation_status,
      coalesce(f.requested_at::date, o.order_date),
      concat_ws(' · ', 'priority ' || lower(f.priority), case when coalesce(f.reminder_count, 0) > 0 then f.reminder_count || ' reminder(s)' end,
                'delivery ' || to_char(o.delivery_date, 'DD-Mon-YYYY')), coalesce(f.requested_at, f.created_at)
      from public.supply_po_confirmations f left join public.supply_purchase_orders o on o.id = f.purchase_order_id
     where f.confirmation_status = 'PENDING';
  elsif k in ('rm_on_order', 'mod_rm_procurement') then
    return query select 'supply_rm_purchase_orders'::text, r.id, coalesce(r.supplier_order_no, po.po_number), co.part_id, r.rm_supplier_id, r.status, coalesce(r.expected_date, r.order_date),
      concat_ws(' · ', public.qcms_kpi_num(r.ordered_qty_kg) || ' kg', 'ordered ' || to_char(r.order_date, 'DD-Mon-YYYY'), 'expected ' || to_char(r.expected_date, 'DD-Mon-YYYY')), r.created_at
      from public.supply_rm_purchase_orders r
      left join public.supply_customer_orders co on co.id = r.customer_order_id
      left join public.supply_purchase_orders po on po.id = r.purchase_order_id
     where r.status = 'OPEN';
  elsif k in ('rm_received_month', 'mod_rm_receipt') then
    return query select 'supply_rm_receipts'::text, r.id, r.receipt_number, co.part_id, rp.rm_supplier_id, 'RECEIVED'::text, r.receipt_date,
      concat_ws(' · ', 'Heat ' || r.heat_number, public.qcms_kpi_num(r.received_qty_kg) || ' kg', 'challan ' || r.supplier_challan), r.created_at
      from public.supply_rm_receipts r
      left join public.supply_customer_orders co on co.id = r.customer_order_id
      left join public.supply_rm_purchase_orders rp on rp.id = r.rm_purchase_order_id
     where r.receipt_date >= v_month;
  elsif k = 'mod_rm_dispatch' then
    return query select 'supply_rm_dispatches'::text, d.id, coalesce(d.dispatch_number, d.challan_number), co.part_id, d.forging_supplier_id, 'DISPATCHED'::text, d.dispatch_date,
      concat_ws(' · ', 'Heat ' || d.heat_number, public.qcms_kpi_num(d.qty_kg) || ' kg', 'vehicle ' || d.vehicle_number), d.created_at
      from public.supply_rm_dispatches d left join public.supply_customer_orders co on co.id = d.customer_order_id
     where d.dispatch_date >= v_month;
  elsif k in ('forging_orders_open', 'mod_forging') then
    return query select 'supply_forging_orders'::text, f.id, coalesce(f.supplier_order_no, po.po_number), co.part_id, f.forging_supplier_id, f.status, coalesce(f.expected_date, f.order_date),
      concat_ws(' · ', public.qcms_kpi_num(f.order_qty_pcs) || ' pcs', 'Heat ' || f.heat_number, 'expected ' || to_char(f.expected_date, 'DD-Mon-YYYY')), f.created_at
      from public.supply_forging_orders f
      left join public.supply_customer_orders co on co.id = f.customer_order_id
      left join public.supply_purchase_orders po on po.id = f.purchase_order_id
     where f.status = 'OPEN';
  elsif k = 'mod_forging_receipts' then
    return query select 'supply_forging_receipts'::text, f.id, f.receipt_number, co.part_id, f.forging_supplier_id, 'RECEIVED'::text, f.receipt_date,
      concat_ws(' · ', public.qcms_kpi_num(f.received_qty_pcs) || ' pcs received', case when coalesce(f.rejected_qty_pcs, 0) > 0 then public.qcms_kpi_num(f.rejected_qty_pcs) || ' rejected' end, 'Heat ' || f.heat_number), f.created_at
      from public.supply_forging_receipts f left join public.supply_customer_orders co on co.id = f.customer_order_id
     where f.receipt_date >= v_month;
  elsif k in ('dispatched_month', 'machined_month', 'fg_month', 'mod_downstream') then
    return query select 'supply_downstream_events'::text, e.id, coalesce(e.reference_no, e.invoice_no), co.part_id, co.customer_id, e.event_type, e.event_date,
      concat_ws(' · ', initcap(replace(e.event_type, '_', ' ')), public.qcms_kpi_num(e.qty_pcs) || ' pcs', 'invoice ' || e.invoice_no, 'Heat ' || e.heat_number), e.created_at
      from public.supply_downstream_events e left join public.supply_customer_orders co on co.id = e.customer_order_id
     where e.event_date >= v_month
       and case k when 'dispatched_month' then e.event_type = 'CUSTOMER_DISPATCH' when 'machined_month' then e.event_type = 'MACHINING'
                  when 'fg_month' then e.event_type = 'FINISHED_GOODS' else true end;
  elsif k = 'mod_indirect_po' then
    v_tab := coalesce(to_regclass('public.supply_indirect_purchase_orders'), to_regclass('public.indirect_purchase_orders'));
    if v_tab is not null then
      begin
        return query execute format($q$
          select %L::text, (j->>'id')::uuid, coalesce(j->>'po_number', j->>'indirect_po_number', j->>'reference_no', left(j->>'id', 8)), null::uuid,
                 nullif(coalesce(j->>'supplier_id', j->>'vendor_id'), '')::uuid, j->>'status', nullif(left(coalesce(j->>'order_date', j->>'created_at'), 10), '')::date,
                 concat_ws(' · ', j->>'description', 'total ' || (j->>'grand_total')), nullif(j->>'created_at', '')::timestamptz
            from (select to_jsonb(t) j from %s t) z
           where coalesce(j->>'status', '') not in ('CLOSED', 'COMPLETED', 'CANCELLED', 'RECEIVED')$q$, replace(v_tab::text, 'public.', ''), v_tab);
      exception when others then
        return;
      end;
    end if;
  -- ---------------------------------------------------------------- Production
  elsif k in ('batch_pcs_available', 'batches_active', 'mod_batches') then
    return query select 'production_batches'::text, b.id, b.batch_code, b.part_id, null::uuid, b.status, b.created_at::date,
      concat_ws(' · ', public.qcms_kpi_num(b.quantity_available) || ' pcs available', 'Heat ' || b.heat_number, 'WO ' || b.work_order), b.created_at
      from public.production_batches b
     where case when k = 'batch_pcs_available' then coalesce(b.quantity_available, 0) <> 0
                else coalesce(b.status, '') not in ('CLOSED', 'CONSUMED', 'CANCELLED') end;
  elsif k in ('osp_at_vendor', 'mod_osp_jobs', 'osp_sample_pending', 'osp_receipt_pending') then
    return query select 'osp_jobs'::text, j.id, j.osp_job_number, j.part_id, j.vendor_id, j.status, j.dispatch_date,
      concat_ws(' · ', public.qcms_kpi_num(j.quantity_dispatched) || ' pcs out', case when coalesce(j.quantity_received, 0) > 0 then public.qcms_kpi_num(j.quantity_received) || ' received' end,
                'return ' || to_char(j.expected_return_date, 'DD-Mon-YYYY'), 'sample ' || lower(j.sample_gate_status), 'receipt QC ' || lower(j.receipt_quality_disposition)), j.created_at
      from public.osp_jobs j
     where case when k in ('osp_at_vendor', 'mod_osp_jobs') then j.status = 'AT_VENDOR'
                when k = 'osp_sample_pending' then coalesce(j.sample_gate_status, '') in ('PENDING', 'ON_HOLD')
                else coalesce(j.receipt_quality_disposition, '') in ('PENDING', 'ON_HOLD') and coalesce(j.quantity_received, 0) > 0 end;
  -- ---------------------------------------------------------------- NPD / APQP
  elsif k in ('npd_open', 'npd_in_progress', 'npd_late', 'mod_npd_orders') then
    return query select 'npd_orders'::text, n.id, n.order_number, n.part_id, n.customer_id, n.status, n.delivery_date,
      concat_ws(' · ', public.qcms_kpi_num(n.order_qty) || ' pcs', 'start ' || to_char(n.start_date, 'DD-Mon-YYYY'), 'delivery ' || to_char(n.delivery_date, 'DD-Mon-YYYY')), n.created_at
      from public.npd_orders n
     where case k when 'npd_open' then n.status = 'OPEN' when 'npd_in_progress' then n.status = 'IN_PROGRESS'
                  when 'npd_late' then coalesce(n.status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED') and n.delivery_date < current_date
                  else coalesce(n.status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED') end;
  elsif k in ('npd_steps_open', 'npd_steps_overdue', 'mod_npd_steps') then
    return query select 'npd_order_steps'::text, s.id, concat_ws(' · OP ', o.order_number, s.operation_no::text), o.part_id, o.customer_id, s.status, s.target_date,
      concat_ws(' · ', coalesce(s.process_name, s.process_name_snapshot), 'responsible ' || s.responsible), s.created_at
      from public.npd_order_steps s left join public.npd_orders o on o.id = s.npd_order_id
     where coalesce(s.status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED')
       and (k <> 'npd_steps_overdue' or s.target_date < current_date);
  elsif k in ('apqp_active', 'apqp_completion', 'mod_apqp') then
    return query select 'ppap_projects'::text, p.id, p.project_code, p.part_id, p.customer_id, p.status, p.target_submission_date,
      concat_ws(' · ', 'PPAP level ' || p.submission_level, public.qcms_kpi_num(p.completion_percent) || '% complete', 'coordinator ' || p.coordinator), p.created_at
      from public.ppap_projects p
     where k = 'apqp_completion' or coalesce(p.status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED', 'APPROVED');
  end if;
end $$;

-- 5 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_records(p_card_key text, p_department text default null, p_limit integer default 500)
returns table(source_table text, record_id uuid, reference text, part text, party text, status text, record_date date, detail text)
language sql stable security invoker set search_path = public as $$
  select b.source_table, b.record_id, coalesce(nullif(b.reference, ''), left(b.record_id::text, 8)),
         nullif(concat_ws(' · ', p.part_number, nullif(p.part_name, '')), ''),
         coalesce(pt.party_name, pt.party_code),
         b.status, b.record_date, nullif(b.detail, '')
    from public.qcms_kpi_base(p_card_key) b
    left join public.parts p on p.id = b.part_id
    left join public.parties pt on pt.id = b.party_id
   order by b.sort_ts desc nulls last, b.record_date desc nulls last
   limit greatest(1, least(coalesce(p_limit, 500), 5000))
$$;

-- 6 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_spark(p_table text, p_date_column text)
returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
  v_out jsonb := '[]'::jsonb;
begin
  if to_regclass('public.' || p_table) is null then
    return v_out;
  end if;
  execute format($q$
    select coalesce(jsonb_agg(coalesce(c, 0) order by m), '[]'::jsonb)
      from generate_series(date_trunc('month', current_date) - interval '5 months', date_trunc('month', current_date), interval '1 month') gs(m)
      left join (select date_trunc('month', %1$I)::date mm, count(*) c from public.%2$I
                  where %1$I >= date_trunc('month', current_date) - interval '5 months' group by 1) x on x.mm = gs.m::date$q$, p_date_column, p_table)
    into v_out;
  return v_out;
exception when others then
  return '[]'::jsonb;
end $$;

-- 7 --------------------------------------------------------------------------------------------
create or replace function public.qcms_module_card(p_key text, p_title text, p_icon text, p_route text, p_module text, p_value numeric,
  p_value_label text, p_overdue numeric, p_overdue_label text, p_month numeric, p_done numeric, p_done_label text, p_spark jsonb,
  p_tone text default null)
returns jsonb language sql immutable set search_path = public as $$
  select jsonb_build_object(
    'key', p_key, 'title', p_title, 'icon', coalesce(p_icon, ''), 'route', p_route, 'module_key', p_module,
    'value', coalesce(p_value, 0), 'value_label', coalesce(p_value_label, ''),
    'overdue', p_overdue, 'overdue_label', p_overdue_label, 'month', p_month, 'done', p_done, 'done_label', p_done_label,
    'progress', case when p_done is not null and coalesce(p_done, 0) + coalesce(p_value, 0) > 0
                     then round(100.0 * p_done / (p_done + coalesce(p_value, 0)), 1) end,
    'spark', coalesce(p_spark, '[]'::jsonb),
    'tone', coalesce(p_tone, case when coalesce(p_overdue, 0) > 0 then 'critical' when coalesce(p_value, 0) > 0 then 'warning' else 'good' end))
$$;

-- 8 --------------------------------------------------------------------------------------------
create or replace function public.qcms_module_cards(p_department text default 'QUALITY')
returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
  v_dept text := upper(coalesce(nullif(trim(p_department), ''), 'QUALITY'));
  v_month date := date_trunc('month', current_date)::date;
  v_cards jsonb := '[]'::jsonb;
  v_pending numeric; v_overdue numeric; v_new numeric; v_done numeric;
begin
  if v_dept in ('SUPPLY', 'SCM', 'SUPPLYCHAIN') then v_dept := 'SUPPLY_CHAIN'; end if;
  if v_dept in ('APQP', 'NPD_APQP') then v_dept := 'NPD'; end if;
  if v_dept not in ('QUALITY', 'SUPPLY_CHAIN', 'PRODUCTION', 'NPD') then v_dept := 'MANAGEMENT'; end if;

  if v_dept = 'QUALITY' then
    -- RMTC
    select count(*), count(*) filter (where created_at < now() - interval '7 days')
      into v_pending, v_overdue from public.rmtc_approvals where coalesce(status, '') not in ('APPROVED', 'REJECTED', 'CANCELLED');
    select count(*) into v_new from public.rmtc_approvals where created_at >= v_month;
    select count(*) into v_done from public.rmtc_approvals where status = 'APPROVED' and coalesce(decision_at, approved_at, updated_at) >= v_month;
    v_cards := v_cards || public.qcms_module_card('mod_rmtc', 'RMTC', '🧾', 'rmtc-records', 'RMTC_ENTRY', v_pending, 'pending decision', v_overdue, '> 7 days', v_new, v_done, 'approved',
                                                  public.qcms_kpi_spark('rmtc_approvals', 'created_at'));
    -- Material inward
    select count(*), count(*) filter (where inward_date < current_date - 7) into v_pending, v_overdue
      from public.inward_lots where status = 'HOLD_PENDING_INSPECTION';
    select count(*) into v_new from public.inward_lots where coalesce(inward_date, created_at::date) >= v_month;
    select count(*) into v_done from public.inward_lots where status = 'RELEASED' and coalesce(released_at, updated_at) >= v_month;
    v_cards := v_cards || public.qcms_module_card('mod_inward', 'Material Inward', '📦', 'inward-records', 'MATERIAL_INWARD', v_pending, 'on quality hold', v_overdue, '> 7 days', v_new, v_done, 'released',
                                                  public.qcms_kpi_spark('inward_lots', 'inward_date'));
    -- MetLAB (in-house) / Bend Test / OSP MetLAB
    select count(*) filter (where status <> 'FINAL' and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is null),
           count(*) filter (where status <> 'FINAL' and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is null and created_at < now() - interval '3 days'),
           count(*) filter (where created_at >= v_month and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is null),
           count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is null)
      into v_pending, v_overdue, v_new, v_done from public.lab_tests;
    v_cards := v_cards || public.qcms_module_card('mod_metlab', 'MetLAB', '🔬', 'metlab-records', 'METLAB_REPORT', v_pending, 'reports pending', v_overdue, '> 3 days', v_new, v_done, 'finalized',
                                                  public.qcms_kpi_spark('lab_tests', 'test_date'));
    select count(*) filter (where status <> 'FINAL' and coalesce(results->>'inspection_method', '') = 'BEND_TEST'),
           count(*) filter (where status <> 'FINAL' and coalesce(results->>'inspection_method', '') = 'BEND_TEST' and created_at < now() - interval '3 days'),
           count(*) filter (where created_at >= v_month and coalesce(results->>'inspection_method', '') = 'BEND_TEST'),
           count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month and coalesce(results->>'inspection_method', '') = 'BEND_TEST')
      into v_pending, v_overdue, v_new, v_done from public.lab_tests;
    v_cards := v_cards || public.qcms_module_card('mod_bend', 'Bend Test', '🧲', 'bend-test-records', 'METLAB_REPORT', v_pending, 'reports pending', v_overdue, '> 3 days', v_new, v_done, 'finalized', null);
    -- Dimensional (in-house) / OSP dimensional
    select count(*) filter (where status <> 'FINAL' and osp_job_id is null),
           count(*) filter (where status <> 'FINAL' and osp_job_id is null and created_at < now() - interval '3 days'),
           count(*) filter (where created_at >= v_month and osp_job_id is null),
           count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month and osp_job_id is null)
      into v_pending, v_overdue, v_new, v_done from public.inspection_reports;
    v_cards := v_cards || public.qcms_module_card('mod_dimensional', 'Dimensional', '📐', 'dimensional-records', 'DIMENSIONAL_REPORT', v_pending, 'reports pending', v_overdue, '> 3 days', v_new, v_done, 'finalized',
                                                  public.qcms_kpi_spark('inspection_reports', 'inspection_date'));
    select count(*) filter (where status <> 'FINAL' and osp_job_id is not null),
           count(*) filter (where status <> 'FINAL' and osp_job_id is not null and created_at < now() - interval '3 days'),
           count(*) filter (where created_at >= v_month and osp_job_id is not null),
           count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month and osp_job_id is not null)
      into v_pending, v_overdue, v_new, v_done from public.inspection_reports;
    v_cards := v_cards || public.qcms_module_card('mod_osp_dimensional', 'OSP Dimensional', '📏', 'osp-records', 'DIMENSIONAL_REPORT', v_pending, 'reports pending', v_overdue, '> 3 days', v_new, v_done, 'finalized', null);
    select count(*) filter (where status <> 'FINAL' and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is not null),
           count(*) filter (where status <> 'FINAL' and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is not null and created_at < now() - interval '3 days'),
           count(*) filter (where created_at >= v_month and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is not null),
           count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month and coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and osp_job_id is not null)
      into v_pending, v_overdue, v_new, v_done from public.lab_tests;
    v_cards := v_cards || public.qcms_module_card('mod_osp_metlab', 'OSP MetLAB', '🧪', 'osp-records', 'METLAB_REPORT', v_pending, 'reports pending', v_overdue, '> 3 days', v_new, v_done, 'finalized', null);
    -- Complaints
    select count(*) filter (where coalesce(status, '') not in ('CLOSED', 'CANCELLED')),
           count(*) filter (where coalesce(status, '') not in ('CLOSED', 'CANCELLED') and target_closure_date < current_date),
           count(*) filter (where complaint_date >= v_month), count(*) filter (where status = 'CLOSED' and closure_date >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.quality_complaints where complaint_type = 'CUSTOMER';
    v_cards := v_cards || public.qcms_module_card('mod_customer_complaints', 'Customer complaints', '📣', 'customer-complaint-register', 'COMPLAINT_MANAGEMENT', v_pending, 'open', v_overdue, 'past target', v_new, v_done, 'closed',
                                                  public.qcms_kpi_spark('quality_complaints', 'complaint_date'));
    select count(*) filter (where coalesce(status, '') not in ('CLOSED', 'CANCELLED')),
           count(*) filter (where coalesce(status, '') not in ('CLOSED', 'CANCELLED') and target_closure_date < current_date),
           count(*) filter (where complaint_date >= v_month), count(*) filter (where status = 'CLOSED' and closure_date >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.quality_complaints where complaint_type = 'SUPPLIER';
    v_cards := v_cards || public.qcms_module_card('mod_supplier_complaints', 'Supplier complaints', '🏭', 'supplier-complaint-register', 'COMPLAINT_MANAGEMENT', v_pending, 'open', v_overdue, 'past target', v_new, v_done, 'closed', null);
    select count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED')),
           count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED') and target_date < current_date),
           count(*) filter (where created_at >= v_month), count(*) filter (where status in ('COMPLETED', 'DONE', 'CLOSED') and completion_date >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.quality_complaint_actions;
    v_cards := v_cards || public.qcms_module_card('mod_capa', 'CAPA actions', '🛠️', 'complaint-analysis', 'COMPLAINT_MANAGEMENT', v_pending, 'actions open', v_overdue, 'past target', v_new, v_done, 'completed', null);
    -- Calibration & validation / standard room / layouts
    select count(*) filter (where least(next_due_date, next_validation_due_date) <= current_date + 30),
           count(*) filter (where least(next_due_date, next_validation_due_date) < current_date)
      into v_pending, v_overdue from public.quality_assets where coalesce(status, 'ACTIVE') = 'ACTIVE';
    select count(*) into v_done from public.quality_asset_calibration_records where service_date >= v_month;
    v_cards := v_cards || public.qcms_module_card('mod_calibration', 'Calibration & validation', '📏', 'calibration-validation', 'CALIBRATION_VALIDATION', v_pending, 'due ≤ 30 days', v_overdue, 'overdue', null, v_done, 'serviced',
                                                  public.qcms_kpi_spark('quality_asset_calibration_records', 'service_date'));
    select count(*) filter (where coalesce(inspection_status, '') in ('PENDING', 'HOLD')),
           count(*) filter (where coalesce(inspection_status, '') in ('PENDING', 'HOLD') and inspection_date < current_date - 3),
           count(*) filter (where inspection_date >= v_month),
           count(*) filter (where coalesce(inspection_status, '') in ('PASS', 'FAIL') and inspection_date >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.standard_room_inspection_records;
    v_cards := v_cards || public.qcms_module_card('mod_standard_room', 'Standard room', '🎯', 'standard-room-inspection', 'CALIBRATION_VALIDATION', v_pending, 'pending / hold', v_overdue, '> 3 days', v_new, v_done, 'completed', null);
    select count(*) filter (where coalesce(status, '') in ('DRAFT', 'APPROVAL_PENDING')),
           count(*) filter (where coalesce(status, '') in ('DRAFT', 'APPROVAL_PENDING') and created_at < now() - interval '7 days'),
           count(*) filter (where created_at >= v_month), count(*) filter (where status = 'APPROVED' and updated_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.inspection_plans;
    v_cards := v_cards || public.qcms_module_card('mod_layouts', 'Inspection layouts', '🗂️', 'inspection-layout-records', 'INSPECTION_LAYOUTS', v_pending, 'draft / approval', v_overdue, '> 7 days', v_new, v_done, 'approved', null);

  elsif v_dept = 'SUPPLY_CHAIN' then
    select count(*) filter (where status in ('OPEN', 'IN_PROGRESS')),
           count(*) filter (where status in ('OPEN', 'IN_PROGRESS') and customer_delivery_date < current_date),
           count(*) filter (where created_at >= v_month), count(*) filter (where status in ('COMPLETED', 'CLOSED') and updated_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.supply_customer_orders;
    v_cards := v_cards || public.qcms_module_card('mod_customer_orders', 'Customer orders / schedules', '🧾', 'supply-customer-orders', 'SUPPLY_CHAIN', v_pending, 'open orders', v_overdue, 'past delivery', v_new, v_done, 'completed',
                                                  public.qcms_kpi_spark('supply_customer_orders', 'created_at'));
    select count(*) filter (where status = 'OPEN'), count(*) filter (where status = 'OPEN' and expected_date < current_date), count(*) filter (where order_date >= v_month)
      into v_pending, v_overdue, v_new from public.supply_rm_purchase_orders;
    select count(*) into v_done from public.supply_rm_receipts where receipt_date >= v_month;
    v_cards := v_cards || public.qcms_module_card('mod_rm_procurement', 'RM procurement', '🛒', 'supply-rm-procurement', 'SUPPLY_CHAIN', v_pending, 'RM orders open', v_overdue, 'past expected', v_new, v_done, 'receipts',
                                                  public.qcms_kpi_spark('supply_rm_purchase_orders', 'order_date'));
    select count(*) filter (where approval_status = 'PENDING_APPROVAL'),
           count(*) filter (where approval_status = 'PENDING_APPROVAL' and coalesce(submitted_at, created_at) < now() - interval '2 days'),
           count(*) filter (where created_at >= v_month), count(*) filter (where approval_status = 'APPROVED' and approved_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.supply_purchase_orders;
    v_cards := v_cards || public.qcms_module_card('mod_po_approval', 'PO pending approval', '✅', 'supply-po-approval', 'SUPPLY_CHAIN', v_pending, 'awaiting approval', v_overdue, '> 2 days', v_new, v_done, 'approved',
                                                  public.qcms_kpi_spark('supply_purchase_orders', 'order_date'));
    select count(*) filter (where confirmation_status = 'PENDING'),
           count(*) filter (where confirmation_status = 'PENDING' and coalesce(requested_at, created_at) < now() - interval '3 days'),
           count(*) filter (where created_at >= v_month), count(*) filter (where confirmation_status = 'CONFIRMED' and confirmed_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.supply_po_confirmations;
    v_cards := v_cards || public.qcms_module_card('mod_po_confirmation', 'PO pending confirmation', '📨', 'supply-po-order-list', 'SUPPLY_CHAIN', v_pending, 'awaiting supplier', v_overdue, '> 3 days', v_new, v_done, 'confirmed', null);
    select count(*) filter (where status in ('OPEN', 'PARTIAL')), count(*) filter (where status in ('OPEN', 'PARTIAL') and delivery_date < current_date),
           count(*) filter (where order_date >= v_month), count(*) filter (where status = 'CLOSED' and updated_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.supply_purchase_orders;
    v_cards := v_cards || public.qcms_module_card('mod_po_open', 'Open purchase orders', '📑', 'supply-po-order-list', 'SUPPLY_CHAIN', v_pending, 'open / partial', v_overdue, 'past delivery', v_new, v_done, 'closed', null);
    select count(*) into v_pending from public.supply_rm_receipts where receipt_date >= v_month;
    select count(*) into v_done from public.supply_rm_receipts where receipt_date >= v_month - interval '1 month' and receipt_date < v_month;
    v_cards := v_cards || public.qcms_module_card('mod_rm_receipt', 'RM receipt', '🚚', 'supply-rm-receipt', 'SUPPLY_CHAIN', v_pending, 'receipts this month', null, null, null, v_done, 'last month',
                                                  public.qcms_kpi_spark('supply_rm_receipts', 'receipt_date'), 'neutral');
    select count(*) into v_pending from public.supply_rm_dispatches where dispatch_date >= v_month;
    select count(*) into v_done from public.supply_rm_dispatches where dispatch_date >= v_month - interval '1 month' and dispatch_date < v_month;
    v_cards := v_cards || public.qcms_module_card('mod_rm_dispatch', 'RM to forging', '🔁', 'supply-rm-dispatch', 'SUPPLY_CHAIN', v_pending, 'dispatches this month', null, null, null, v_done, 'last month',
                                                  public.qcms_kpi_spark('supply_rm_dispatches', 'dispatch_date'), 'neutral');
    select count(*) filter (where status = 'OPEN'), count(*) filter (where status = 'OPEN' and expected_date < current_date), count(*) filter (where order_date >= v_month)
      into v_pending, v_overdue, v_new from public.supply_forging_orders;
    select count(*) into v_done from public.supply_forging_receipts where receipt_date >= v_month;
    v_cards := v_cards || public.qcms_module_card('mod_forging', 'Forging orders / receipts', '🔨', 'supply-forging', 'SUPPLY_CHAIN', v_pending, 'forging orders open', v_overdue, 'past expected', v_new, v_done, 'receipts',
                                                  public.qcms_kpi_spark('supply_forging_receipts', 'receipt_date'));
    select count(*) into v_pending from public.supply_downstream_events where event_date >= v_month;
    select count(*) into v_done from public.supply_downstream_events where event_date >= v_month - interval '1 month' and event_date < v_month;
    v_cards := v_cards || public.qcms_module_card('mod_downstream', 'Machining / FG / dispatch', '🏁', 'supply-downstream', 'SUPPLY_CHAIN', v_pending, 'events this month', null, null, null, v_done, 'last month',
                                                  public.qcms_kpi_spark('supply_downstream_events', 'event_date'), 'neutral');
    select count(*) filter (where status = 'AT_VENDOR'), count(*) filter (where status = 'AT_VENDOR' and expected_return_date < current_date),
           count(*) filter (where dispatch_date >= v_month), count(*) filter (where status = 'COMPLETED' and receipt_date >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.osp_jobs;
    v_cards := v_cards || public.qcms_module_card('mod_osp_jobs', 'OSP jobs at vendor', '🏭', 'osp-records', 'OSP_TRANSACTIONS', v_pending, 'jobs at vendor', v_overdue, 'past return date', v_new, v_done, 'completed',
                                                  public.qcms_kpi_spark('osp_jobs', 'dispatch_date'));
    if coalesce(to_regclass('public.supply_indirect_purchase_orders'), to_regclass('public.indirect_purchase_orders')) is not null then
      select count(*) into v_pending from public.qcms_kpi_base('mod_indirect_po');
      v_cards := v_cards || public.qcms_module_card('mod_indirect_po', 'Indirect purchase', '🧰', 'indirect-po', 'SUPPLY_CHAIN', v_pending, 'open', null, null, null, null, null, null);
    end if;

  elsif v_dept = 'PRODUCTION' then
    select count(*) filter (where coalesce(status, '') not in ('CLOSED', 'CONSUMED', 'CANCELLED')), count(*) filter (where created_at >= v_month)
      into v_pending, v_new from public.production_batches;
    v_cards := v_cards || public.qcms_module_card('mod_batches', 'Production batches', '⚙️', 'osp-records', 'OSP_TRANSACTIONS', v_pending, 'active batches', null, null, v_new, null, null,
                                                  public.qcms_kpi_spark('production_batches', 'created_at'), 'neutral');
    select count(*) filter (where status = 'AT_VENDOR'), count(*) filter (where status = 'AT_VENDOR' and expected_return_date < current_date),
           count(*) filter (where dispatch_date >= v_month), count(*) filter (where status = 'COMPLETED' and receipt_date >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.osp_jobs;
    v_cards := v_cards || public.qcms_module_card('mod_osp_jobs', 'OSP jobs at vendor', '🏭', 'osp-records', 'OSP_TRANSACTIONS', v_pending, 'jobs at vendor', v_overdue, 'past return date', v_new, v_done, 'completed',
                                                  public.qcms_kpi_spark('osp_jobs', 'dispatch_date'));
    select count(*) filter (where coalesce(sample_gate_status, '') in ('PENDING', 'ON_HOLD')),
           count(*) filter (where coalesce(sample_gate_status, '') in ('PENDING', 'ON_HOLD') and sample_received_date < current_date - 3)
      into v_pending, v_overdue from public.osp_jobs;
    v_cards := v_cards || public.qcms_module_card('osp_sample_pending', 'OSP sample gate', '🧪', 'osp-sample-receipt', 'OSP_TRANSACTIONS', v_pending, 'sample pending / hold', v_overdue, '> 3 days', null, null, null, null);
    select count(*) filter (where coalesce(receipt_quality_disposition, '') in ('PENDING', 'ON_HOLD') and coalesce(quantity_received, 0) > 0),
           count(*) filter (where coalesce(receipt_quality_disposition, '') in ('PENDING', 'ON_HOLD') and coalesce(quantity_received, 0) > 0 and receipt_date < current_date - 3)
      into v_pending, v_overdue from public.osp_jobs;
    v_cards := v_cards || public.qcms_module_card('osp_receipt_pending', 'OSP receipt quality', '📥', 'osp-dimensional', 'OSP_TRANSACTIONS', v_pending, 'receipt QC pending', v_overdue, '> 3 days', null, null, null, null);
    select count(*) into v_pending from public.supply_downstream_events where event_date >= v_month;
    select count(*) into v_done from public.supply_downstream_events where event_date >= v_month - interval '1 month' and event_date < v_month;
    v_cards := v_cards || public.qcms_module_card('mod_downstream', 'Machining / FG / dispatch', '🏁', 'supply-downstream', 'SUPPLY_CHAIN', v_pending, 'events this month', null, null, null, v_done, 'last month',
                                                  public.qcms_kpi_spark('supply_downstream_events', 'event_date'), 'neutral');

  elsif v_dept = 'NPD' then
    select count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED')),
           count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED') and delivery_date < current_date),
           count(*) filter (where created_at >= v_month), count(*) filter (where status in ('COMPLETED', 'CLOSED') and updated_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.npd_orders;
    v_cards := v_cards || public.qcms_module_card('mod_npd_orders', 'NPD orders', '🧭', 'npd-status', 'NPD_APQP', v_pending, 'open / in progress', v_overdue, 'late', v_new, v_done, 'completed',
                                                  public.qcms_kpi_spark('npd_orders', 'order_date'));
    select count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED')),
           count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED') and target_date < current_date),
           count(*) filter (where status in ('COMPLETED', 'DONE') and completed_date >= v_month)
      into v_pending, v_overdue, v_done from public.npd_order_steps;
    v_cards := v_cards || public.qcms_module_card('mod_npd_steps', 'NPD steps', '🪜', 'npd-status', 'NPD_APQP', v_pending, 'steps open', v_overdue, 'overdue', null, v_done, 'completed', null);
    select count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED', 'APPROVED')),
           count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED', 'APPROVED') and target_submission_date < current_date),
           count(*) filter (where created_at >= v_month), count(*) filter (where status in ('COMPLETED', 'APPROVED') and updated_at >= v_month)
      into v_pending, v_overdue, v_new, v_done from public.ppap_projects;
    v_cards := v_cards || public.qcms_module_card('mod_apqp', 'APQP / PPAP projects', '📋', 'apqp', 'NPD_APQP', v_pending, 'active projects', v_overdue, 'past target', v_new, v_done, 'approved', null);

  else  -- MANAGEMENT: one highlight per area
    select count(*) into v_pending from public.qcms_kpi_base('mod_quality_reports');
    select count(*) into v_done from public.qcms_kpi_base('reports_final_month');
    v_cards := v_cards || public.qcms_module_card('mod_quality_reports', 'Quality reports', '🔬', 'records-center', 'METLAB_REPORT', v_pending, 'MetLAB / Bend / Dim pending', null, null, null, v_done, 'finalized', null);
    select count(*), count(*) filter (where target_closure_date < current_date) into v_pending, v_overdue
      from public.quality_complaints where coalesce(status, '') not in ('CLOSED', 'CANCELLED');
    v_cards := v_cards || public.qcms_module_card('complaints_open', 'Complaints', '📣', 'complaint-records', 'COMPLAINT_MANAGEMENT', v_pending, 'open', v_overdue, 'past target', null, null, null,
                                                  public.qcms_kpi_spark('quality_complaints', 'complaint_date'));
    select count(*) into v_pending from public.supply_purchase_orders where approval_status = 'PENDING_APPROVAL';
    v_cards := v_cards || public.qcms_module_card('mod_po_approval', 'PO approvals', '✅', 'supply-po-approval', 'SUPPLY_CHAIN', v_pending, 'awaiting approval', null, null, null, null, null, null);
    select count(*), count(*) filter (where customer_delivery_date < current_date) into v_pending, v_overdue
      from public.supply_customer_orders where status in ('OPEN', 'IN_PROGRESS');
    v_cards := v_cards || public.qcms_module_card('mod_customer_orders', 'Customer orders', '🧾', 'supply-customer-orders', 'SUPPLY_CHAIN', v_pending, 'open orders', v_overdue, 'past delivery', null, null, null, null);
    select count(*) into v_pending from public.quality_assets
     where coalesce(status, 'ACTIVE') = 'ACTIVE' and least(next_due_date, next_validation_due_date) < current_date;
    v_cards := v_cards || public.qcms_module_card('calibration_overdue', 'Calibration overdue', '📏', 'calibration-validation', 'CALIBRATION_VALIDATION', v_pending, 'assets overdue', null, null, null, null, null, null);
    select count(*) into v_pending from public.npd_orders where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED') and delivery_date < current_date;
    v_cards := v_cards || public.qcms_module_card('npd_late', 'NPD late', '🧭', 'npd-status', 'NPD_APQP', v_pending, 'orders late', null, null, null, null, null, null);
  end if;

  return jsonb_build_object('department', v_dept, 'generated_at', now(), 'modules', v_cards);
end $$;

-- 9 · grants -----------------------------------------------------------------------------------
revoke all on function public.qcms_kpi_base(text) from public, anon;
grant execute on function public.qcms_kpi_base(text) to authenticated;
revoke all on function public.qcms_kpi_records(text, text, integer) from public, anon;
grant execute on function public.qcms_kpi_records(text, text, integer) to authenticated;
revoke all on function public.qcms_kpi_spark(text, text) from public, anon;
grant execute on function public.qcms_kpi_spark(text, text) to authenticated;
revoke all on function public.qcms_module_cards(text) from public, anon;
grant execute on function public.qcms_module_cards(text) to authenticated;
grant execute on function public.qcms_module_card(text, text, text, text, text, numeric, text, numeric, text, numeric, numeric, text, jsonb, text) to authenticated;
grant execute on function public.qcms_kpi_card_k(text, text, numeric, text, text, text) to authenticated;
grant execute on function public.qcms_kpi_num(numeric) to authenticated;
revoke all on function public.qcms_kpi_dashboard(text) from public, anon;
grant execute on function public.qcms_kpi_dashboard(text) to authenticated;

notify pgrst, 'reload schema';
