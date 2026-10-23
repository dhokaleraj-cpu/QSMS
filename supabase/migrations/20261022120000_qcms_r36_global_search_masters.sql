-- QCMS v4.14.49 R36 · Global Search covers every master and detail table, masters ranked first.
-- Re-runnable: create or replace only (same signatures as R35).
create or replace function public.qcms_search_table_map()
returns jsonb language sql immutable set search_path = public as $$
  select '{
    "parts": ["PART_MASTER", "Part Master", "part-records"],
    "part_raw_material_details": ["PART_MASTER", "Part Raw Material", "part-records"],
    "part_raw_material_technical_data": ["PART_MASTER", "Part RM Technical Data", "part-records"],
    "part_supplier_links": ["PART_MASTER", "Part Supplier", "part-records"],
    "part_supplier_price_history": ["PART_MASTER", "Part Supplier Price", "part-records"],
    "part_process_specifications": ["PART_MASTER", "Part Process Specification", "part-records"],
    "part_process_parameter_specifications": ["PART_MASTER", "Part Process Parameter", "part-records"],
    "part_metallurgical_requirements": ["PART_MASTER", "Part Metallurgical Requirement", "part-records"],
    "part_heat_treatment_details": ["PART_MASTER", "Part Heat Treatment", "part-records"],
    "part_rmtc_requirements": ["PART_MASTER", "Part RMTC Requirement", "part-records"],
    "parties": ["REFERENCE_MASTERS", "Customer / Supplier / Vendor", "reference-records"],
    "company_branches": ["REFERENCE_MASTERS", "Company Branch", "company-branch-records"],
    "material_grades": ["MATERIAL_GRADE", "Material Grade", "grade-records"],
    "processes": ["REFERENCE_MASTERS", "Process Master", "process-records"],
    "inspection_stages": ["REFERENCE_MASTERS", "Inspection Stage", "reference-records"],
    "employees": ["EMPLOYEE_MASTER", "Employee", "employee-records"],
    "inspection_plans": ["INSPECTION_LAYOUTS", "Inspection Layout", "inspection-layout-records"],
    "inspection_plan_characteristics": ["INSPECTION_LAYOUTS", "Layout Characteristic", "inspection-layout-records"],
    "rmtc_approvals": ["RMTC_ENTRY", "RMTC", "rmtc-records"],
    "rmtc_part_approvals": ["RMTC_ENTRY", "RMTC Part Approval", "rmtc-records"],
    "inward_lots": ["MATERIAL_INWARD", "Material Inward", "inward-records"],
    "production_batches": ["OSP_TRANSACTIONS", "Production / FSI Batch", "osp-records"],
    "osp_jobs": ["OSP_TRANSACTIONS", "OSP Job / Material Out", "osp-records"],
    "osp_receipts": ["OSP_TRANSACTIONS", "OSP Inward Receipt", "osp-records"],
    "osp_material_outs": ["OSP_TRANSACTIONS", "OSP Material Out", "osp-records"],
    "inspection_reports": ["DIMENSIONAL_REPORT", "Dimensional Report", "dimensional-records"],
    "inspection_results": ["DIMENSIONAL_REPORT", "Dimensional Result", "dimensional-records"],
    "lab_tests": ["METLAB_REPORT", "MetLAB / Bend Test Report", "metlab-records"],
    "quality_complaints": ["COMPLAINT_MANAGEMENT", "Quality Complaint", "complaint-records"],
    "quality_complaint_actions": ["COMPLAINT_MANAGEMENT", "Complaint Action", "complaint-records"],
    "quality_complaint_followups": ["COMPLAINT_MANAGEMENT", "Complaint Follow-up", "complaint-records"],
    "supply_customer_orders": ["SUPPLY_CHAIN", "Customer Order / Schedule", "supply-customer-orders"],
    "supply_purchase_orders": ["SUPPLY_CHAIN", "Purchase Order", "supply-po-order-list"],
    "supply_purchase_order_items": ["SUPPLY_CHAIN", "Purchase Order Item", "supply-po-order-list"],
    "supply_rm_purchase_orders": ["SUPPLY_CHAIN", "RM Procurement Order", "supply-rm-procurement"],
    "supply_rm_receipts": ["SUPPLY_CHAIN", "RM Receipt", "supply-rm-receipt"],
    "supply_rm_dispatches": ["SUPPLY_CHAIN", "RM to Forging", "supply-rm-dispatch"],
    "supply_forging_orders": ["SUPPLY_CHAIN", "Forging Order", "supply-forging"],
    "supply_forging_receipts": ["SUPPLY_CHAIN", "Forging Receipt", "supply-forging"],
    "supply_downstream_events": ["SUPPLY_CHAIN", "Machining / FG / Dispatch", "supply-downstream"],
    "supply_opening_stock": ["SUPPLY_CHAIN", "Opening Stock", "supply-opening-stock"],
    "supply_po_confirmations": ["SUPPLY_CHAIN", "PO Confirmation", "supply-po-order-list"],
    "npd_orders": ["NPD_APQP", "NPD Order", "npd-status"],
    "npd_order_steps": ["NPD_APQP", "NPD Step", "npd-status"],
    "npd_process_flows": ["NPD_APQP", "Process Flow", "npd-process-flow"],
    "npd_process_flow_steps": ["NPD_APQP", "Process Flow Step", "npd-process-flow"],
    "ppap_projects": ["NPD_APQP", "APQP / PPAP Project", "apqp"],
    "ppap_documents": ["NPD_APQP", "PPAP Document", "apqp"],
    "quality_assets": ["CALIBRATION_VALIDATION", "Gauge / Fixture / Instrument", "calibration-validation"],
    "quality_asset_calibration_records": ["CALIBRATION_VALIDATION", "Calibration / Validation Record", "calibration-validation"],
    "standard_room_inspection_records": ["CALIBRATION_VALIDATION", "Standard Room Inspection", "standard-room-inspection"],
    "standard_room_inspections": ["CALIBRATION_VALIDATION", "Standard Room Inspection", "standard-room-inspection"],
    "standard_room_instruments": ["CALIBRATION_VALIDATION", "Standard Room Instrument", "standard-room-inspection"],
    "customer_standards": ["REFERENCE_MASTERS", "Customer Standard", "standards-records"],
    "standards_register": ["REFERENCE_MASTERS", "Standards Register", "standards-records"],
    "qc_calculation_records": ["QC_CALCULATION_TOOLS", "QC Calculation", "qc-calculation-records"],
    "material_grade_elements": ["MATERIAL_GRADE", "Material Grade Chemistry", "grade-records"],
    "part_material_grade_links": ["PART_MASTER", "Part Material Grade", "part-records"],
    "part_jominy_requirements": ["PART_MASTER", "Part Jominy Requirement", "part-records"],
    "part_standard_links": ["PART_MASTER", "Part Standard Link", "part-records"],
    "test_plans": ["INSPECTION_LAYOUTS", "Test Plan", "inspection-layout-records"],
    "gauge_fixture_assets": ["CALIBRATION_VALIDATION", "Gauge / Fixture", "calibration-validation"],
    "gauge_fixture_control_records": ["CALIBRATION_VALIDATION", "Gauge / Fixture Control Record", "calibration-validation"],
    "quality_asset_part_process_links": ["CALIBRATION_VALIDATION", "Gauge Part / Process Link", "calibration-validation"],
    "calibration_events": ["CALIBRATION_VALIDATION", "Calibration Event", "calibration-validation"],
    "rmtc_chemistry_results": ["RMTC_ENTRY", "RMTC Chemistry Result", "rmtc-records"],
    "rmtc_requirement_results": ["RMTC_ENTRY", "RMTC Requirement Result", "rmtc-records"],
    "rmtc_jominy_results": ["RMTC_ENTRY", "RMTC Jominy Result", "rmtc-records"],
    "rmtc_decision_revisions": ["RMTC_ENTRY", "RMTC Decision Revision", "rmtc-records"],
    "supply_purchase_order_sources": ["SUPPLY_CHAIN", "PO Customer Order Source", "supply-po-order-list"],
    "batch_movements": ["OSP_TRANSACTIONS", "Batch Movement", "osp-records"],
    "dispatches": ["SUPPLY_CHAIN", "Dispatch", "supply-downstream"],
    "dispatch_batches": ["SUPPLY_CHAIN", "Dispatch Batch", "supply-downstream"],
    "customer_report_packages": ["DIMENSIONAL_REPORT", "Customer Report Package", "records-center"],
    "customer_report_package_items": ["DIMENSIONAL_REPORT", "Customer Report Package Item", "records-center"],
    "control_plan_headers": ["NPD_APQP", "Control Plan", "apqp"],
    "control_plan_items": ["NPD_APQP", "Control Plan Item", "apqp"],
    "pfd_headers": ["NPD_APQP", "Process Flow Diagram", "apqp"],
    "pfd_steps": ["NPD_APQP", "PFD Step", "apqp"],
    "pfmea_headers": ["NPD_APQP", "PFMEA", "apqp"],
    "pfmea_items": ["NPD_APQP", "PFMEA Item", "apqp"],
    "msa_plans": ["NPD_APQP", "MSA Plan", "apqp"],
    "msa_studies": ["NPD_APQP", "MSA Study", "apqp"],
    "spc_plans": ["NPD_APQP", "SPC Plan", "apqp"],
    "spc_studies": ["NPD_APQP", "SPC Study", "apqp"],
    "capacity_studies": ["NPD_APQP", "Capacity Study", "apqp"],
    "balloon_characteristics": ["NPD_APQP", "Balloon Characteristic", "apqp"],
    "npd_order_step_points": ["NPD_APQP", "NPD Step Point", "npd-status"],
    "npd_process_flow_points": ["NPD_APQP", "Process Flow Point", "npd-process-flow"],
    "audit_plans": [null, "Audit Plan", "records-center"],
    "audit_findings": [null, "Audit Finding", "records-center"],
    "document_approvals": [null, "Document Approval", "records-center"],
    "calculation_rules": ["QC_CALCULATION_TOOLS", "Calculation Rule", "qc-tools"],
    "document_attachments": [null, "Attachment / Photo", "records-center"],
    "qcms_delete_requests": [null, "Deletion Request", "records-center"]
  }'::jsonb
$$;

create or replace function public.qcms_global_search(p_query text, p_limit integer default 200)
returns table(source_table text, record_id uuid, module_key text, title text, subtitle text, matched_field text, snippet text, web_route text, record_type text)
language plpgsql volatile security invoker set search_path = public set statement_timeout = '15s' as $$
declare
  v_q text := btrim(coalesce(p_query, ''));
  v_pat text;
  v_limit integer := least(greatest(coalesce(p_limit, 200), 10), 1000);
  v_per integer;
  v_map jsonb := public.qcms_search_table_map();
  v_out jsonb := '[]'::jsonb;
  v_chunk jsonb;
  v_part_ids uuid[] := '{}';
  v_party_ids uuid[] := '{}';
  t record;
  v_cols text[];
  v_title text;
  v_sub text;
  v_where text;
  v_case_f text;
  v_case_s text;
  v_sql text;
  v_entry jsonb;
  v_rel text[];
  c text;
begin
  if length(v_q) < 2 then return; end if;
  v_pat := '%' || replace(replace(replace(v_q, '\', '\\'), '%', '\%'), '_', '\_') || '%';
  v_per := least(greatest(v_limit / 8, 8), 50);

  select coalesce(array_agg(id), '{}') into v_part_ids from (
    select id from public.parts where part_number ilike v_pat or fsi_part_number ilike v_pat or part_name ilike v_pat or drawing_number ilike v_pat limit 50) x;
  select coalesce(array_agg(id), '{}') into v_party_ids from (
    select id from public.parties where party_code ilike v_pat or party_name ilike v_pat limit 50) x;

  for t in
    select cl.relname::text as tbl, cl.oid
      from pg_class cl join pg_namespace n on n.oid = cl.relnamespace
     where n.nspname = 'public' and cl.relkind = 'r'
       and exists (select 1 from pg_attribute a where a.attrelid = cl.oid and a.attname = 'id' and a.atttypid = 'uuid'::regtype and not a.attisdropped)
       and exists (select 1 from pg_attribute a where a.attrelid = cl.oid and a.attname = 'tenant_id' and not a.attisdropped)
       and has_table_privilege(cl.oid, 'SELECT')
       and cl.relname not in ('audit_log', 'qcms_user_mail_accounts', 'qcms_email_settings', 'qcms_email_templates', 'qcms_mail_groups',
           'qcms_mail_sent_log', 'qcms_notification_outbox', 'qcms_notification_routes', 'qcms_notification_schedules',
           'qcms_notification_scheduler_config', 'qcms_password_edit_audit', 'qcms_user_activity_log', 'qcms_module_approval_routes',
           'number_sequences', 'heat_code_sequences', 'master_value_catalog', 'profiles', 'user_module_permissions',
           'user_section_permissions', 'role_module_defaults', 'department_module_defaults', 'qcms_user_dashboards',
           'qcms_user_notifications', 'qcms_push_devices', 'supply_stage_responsibilities')
       and cl.relname not like 'stawn\_%' and cl.relname not like '%licen%' and cl.relname not like '%whatsapp%'
     order by case
                when cl.relname in ('parts', 'parties', 'material_grades', 'processes', 'employees', 'company_branches', 'inspection_stages',
                                    'customer_standards', 'standards_register', 'quality_assets', 'inspection_plans', 'test_plans',
                                    'material_grade_elements', 'gauge_fixture_assets') then 0
                when cl.relname like 'part\_%' then 1
                when cl.relname in ('supply_customer_orders', 'supply_purchase_orders', 'rmtc_approvals', 'inward_lots', 'lab_tests',
                                    'inspection_reports', 'osp_jobs', 'quality_complaints', 'npd_orders', 'ppap_projects') then 2
                when v_map ? cl.relname then 3 else 4 end, cl.relname
  loop
    exit when jsonb_array_length(v_out) >= v_limit;
    select coalesce(array_agg(a.attname::text order by a.attnum), '{}') into v_cols
      from pg_attribute a
     where a.attrelid = t.oid and a.attnum > 0 and not a.attisdropped
       and a.atttypid in ('text'::regtype, 'varchar'::regtype, 'bpchar'::regtype)
       and a.attname not like '%password%' and a.attname not like '%secret%' and a.attname not like '%token%'
       and a.attname not like '%\_path' and a.attname not in ('checksum', 'api_key', 'smtp_password', 'mime_type');
    v_entry := coalesce(v_map -> t.tbl, jsonb_build_array(null, initcap(replace(t.tbl, '_', ' ')), 'records-center'));

    -- title / subtitle from the best reference columns this table has
    select coalesce('coalesce(' || string_agg(format('nullif(btrim(t.%I::text), %L)', col, ''), ', ' order by ord) || ', t.id::text)', 't.id::text') into v_title
      from unnest(array['part_number', 'po_number', 'report_number', 'rmtc_number', 'inward_number', 'complaint_number', 'osp_job_number',
                        'receipt_number', 'dispatch_number', 'batch_code', 'customer_order_no', 'master_reference_no', 'supplier_order_no',
                        'order_number', 'project_code', 'plan_number', 'asset_code', 'asset_number', 'party_code', 'grade_code',
                        'process_code', 'employee_code', 'certificate_number', 'reference_no', 'document_title', 'file_name',
                        'record_label', 'standard_number', 'heat_number', 'name', 'title', 'code']) with ordinality u(col, ord)
     where col = any(v_cols);
    select coalesce('concat_ws('' · '', ' || string_agg(format('nullif(btrim(t.%I::text), %L)', col, ''), ', ' order by ord) || ')', '''''') into v_sub
      from unnest(array['part_name', 'party_name', 'layout_name', 'asset_name', 'subject', 'heat_number', 'process_name', 'first_name',
                        'last_name', 'test_type', 'report_type', 'event_type', 'status']) with ordinality u(col, ord)
     where col = any(v_cols);

    v_rel := '{}';
    if v_part_ids <> '{}' and exists (select 1 from pg_attribute a where a.attrelid = t.oid and a.attname = 'part_id' and a.atttypid = 'uuid'::regtype and not a.attisdropped)
       and t.tbl <> 'parts' then
      v_rel := array_append(v_rel, 't.part_id = any($2)'::text);
    end if;
    if v_party_ids <> '{}' then
      for c in select a.attname::text from pg_attribute a where a.attrelid = t.oid and not a.attisdropped and a.atttypid = 'uuid'::regtype
                 and a.attname in ('customer_id', 'supplier_id', 'party_id', 'vendor_id', 'forging_supplier_id', 'rm_supplier_id', 'steel_mill_id', 'osp_vendor_id', 'ship_to_party_id')
      loop
        v_rel := array_append(v_rel, format('t.%I = any($3)', c));
      end loop;
    end if;

    if coalesce(array_length(v_cols, 1), 0) = 0 and coalesce(array_length(v_rel, 1), 0) = 0 then continue; end if;

    select string_agg(format('t.%I ilike $1', col), ' or ') into v_where from unnest(v_cols) col;
    select 'case ' || string_agg(format('when t.%I ilike $1 then %L', col, col), ' ') || ' else ''related part / party'' end' into v_case_f from unnest(v_cols) col;
    select 'case ' || string_agg(format('when t.%I ilike $1 then left(t.%I::text, 180)', col, col), ' ') || ' else null end' into v_case_s from unnest(v_cols) col;
    v_where := concat_ws(' or ', nullif(v_where, ''), nullif(array_to_string(v_rel, ' or '), ''));
    v_case_f := coalesce(v_case_f, '''related part / party''');
    v_case_s := coalesce(v_case_s, 'null');

    v_sql := format(
      'select coalesce(jsonb_agg(jsonb_build_object(''source_table'', %L, ''record_id'', x.id, ''module_key'', %L, ''title'', x.ti, ''subtitle'', x.su,'
      || ' ''matched_field'', x.mf, ''snippet'', x.sn, ''web_route'', %L, ''record_type'', %L)), ''[]''::jsonb)'
      || ' from (select t.id, (%s)::text ti, (%s)::text su, (%s)::text mf, (%s)::text sn from public.%I t where %s limit %s) x',
      t.tbl, v_entry ->> 0, v_entry ->> 2, v_entry ->> 1, v_title, v_sub, v_case_f, v_case_s, t.tbl, v_where, v_per);
    begin
      execute v_sql into v_chunk using v_pat, v_part_ids, v_party_ids;
    exception when others then
      v_chunk := '[]'::jsonb;  -- one unusual table must never break Global Search
    end;
    v_out := v_out || coalesce(v_chunk, '[]'::jsonb);
  end loop;

  return query
    select e->>'source_table', (e->>'record_id')::uuid, e->>'module_key',
           case when e->>'title' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-' then coalesce(nullif(left(e->>'snippet', 80), ''), e->>'record_type') else e->>'title' end,
           e->>'subtitle', e->>'matched_field',
           case when e->>'matched_field' = 'related part / party' then null else e->>'snippet' end, e->>'web_route', e->>'record_type'
      from jsonb_array_elements(v_out) e
     order by case when lower(e->>'title') = lower(v_q) then 0 when e->>'title' ilike v_q || '%' then 1
                   when e->>'matched_field' = 'related part / party' then 3 else 2 end,
              e->>'record_type', e->>'title'
     limit v_limit;
end $$;

revoke all on function public.qcms_global_search(text, integer) from public, anon;
grant execute on function public.qcms_global_search(text, integer) to authenticated;
grant execute on function public.qcms_search_table_map() to authenticated;
notify pgrst, 'reload schema';
