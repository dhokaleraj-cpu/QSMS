-- QCMS v4.14.49 R37 · module infographic KPIs + one drill-down contract for every KPI card.
-- Idempotent and additive: create or replace function only. Data-reading functions are SECURITY INVOKER,
-- so the base-table RLS (tenant isolation) decides what each user counts and lists.
--
--  1. public.qcms_kpi_definitions()            - module KPI definitions (generated from core/module_kpis.py)
--  2. public.qcms_kpi_col(jsonb, text)         - column reference of the filter language (identifiers quoted)
--  3. public.qcms_kpi_where(jsonb, text)       - JSON filter -> SQL predicate (literals quoted, two-valued)
--  4. public.qcms_kpi_drill_spec(text)         - the "drill" object of a card key (web + mobile contract)
--     public.qcms_kpi_drill_spec_from(text, jsonb) - same, with the definitions already loaded
--  5. public.qcms_kpi_card_k / qcms_module_card - start-dashboard + module-strip cards now carry "drill"
--  6. public.qcms_module_kpis(text, text[])    - module groups with 3-6 KPI cards each (+ 6-month trend)
--  7. public.qcms_kpi_drilldown(text, integer) - rows behind ANY card key (same filter as the count)
--
-- Card count == drill row count: both are generated from the same JSON filter by qcms_kpi_where.

-- 1 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_definitions()
returns jsonb language sql immutable set search_path = public as $fn$
  select $qcmsdefs${"version":1,
"groups":[
{"base":[{"col":"results.inspection_method","op":"neq","value":"BEND_TEST"},{"col":"osp_job_id","op":"blank"}],"date":"test_date","department":"QUALITY","detail":[["Heat","heat_number"],["Decision","disposition"],["Layout","layout_name_snapshot"]],"entry_route":"metlab-entry","icon":"🔬","key":"metlab","metrics":["mk_metlab_pending","mk_metlab_overdue","mk_metlab_month","mk_metlab_final_month","mk_metlab_reserve_month","mk_metlab_rejected_pct"],"module_key":"METLAB_REPORT","part":"part_id","party":["supplier_id","customer_id"],"ref":["report_number"],"route":"metlab-records","spark":"created_at","status":"status","table":"lab_tests","title":"MetLAB"},
{"base":[{"col":"osp_job_id","op":"blank"}],"date":"inspection_date","department":"QUALITY","detail":[["Heat","heat_number"],["Decision","disposition"],["Scope","inspection_scope"]],"entry_route":"dimensional-entry","icon":"📐","key":"dimensional","metrics":["mk_dimensional_pending","mk_dimensional_overdue","mk_dimensional_month","mk_dimensional_final_month","mk_dimensional_reserve_month","mk_dimensional_rejected_pct"],"module_key":"DIMENSIONAL_REPORT","part":"part_id","party":["supplier_id","customer_id"],"ref":["report_number"],"route":"dimensional-records","spark":"created_at","status":"status","table":"inspection_reports","title":"Dimensional"},
{"base":[{"col":"results.inspection_method","op":"eq","value":"BEND_TEST"}],"date":"test_date","department":"QUALITY","detail":[["Heat","heat_number"],["Decision","disposition"]],"entry_route":"bend-test-entry","icon":"🧲","key":"bend","metrics":["mk_bend_pending","mk_bend_overdue","mk_bend_month","mk_bend_final_month","mk_bend_reserve_month","mk_bend_rejected_pct"],"module_key":"METLAB_REPORT","part":"part_id","party":["supplier_id","customer_id"],"ref":["report_number"],"route":"bend-test-records","spark":"created_at","status":"status","table":"lab_tests","title":"Bend Test"},
{"base":[],"date":"certificate_date","department":"QUALITY","detail":[["Heat","heat_number"],["Validation","validation_result"],["Decision","disposition"]],"entry_route":"rmtc-entry","icon":"🧾","key":"rmtc","metrics":["mk_rmtc_pending","mk_rmtc_overdue","mk_rmtc_approval","mk_rmtc_approved_month","mk_rmtc_reserve","mk_rmtc_rejected_month"],"module_key":"RMTC_ENTRY","part":"part_id","party":["supplier_id","steel_mill_id"],"ref":["rmtc_number","certificate_reference"],"route":"rmtc-records","spark":"created_at","status":"status","table":"rmtc_approvals","title":"RMTC"},
{"base":[],"date":"inward_date","department":"QUALITY","detail":[["Heat","heat_number"],["MetLAB","metallurgical_status"],["Dim","dimensional_status"]],"entry_route":"inward-entry","icon":"📦","key":"inward","metrics":["mk_inward_hold","mk_inward_hold_old","mk_inward_month","mk_inward_released_month","mk_inward_reserve"],"module_key":"MATERIAL_INWARD","part":"part_id","party":["supplier_id"],"ref":["inward_number","grn_number"],"route":"inward-records","spark":"inward_date","status":"status","table":"inward_lots","title":"Material Inward"},
{"base":[],"date":"dispatch_date","department":"QUALITY","detail":[["Challan","dispatch_challan"],["Sample","sample_gate_status"],["Receipt QC","receipt_quality_disposition"]],"entry_route":"osp-material-out","icon":"🏭","key":"osp","metrics":["mk_osp_at_vendor","mk_osp_overdue","mk_osp_sample","mk_osp_receipt_qc","mk_osp_completed_month","mk_osp_rejected"],"module_key":"OSP_TRANSACTIONS","part":"part_id","party":["vendor_id"],"ref":["osp_job_number","dispatch_challan"],"route":"osp-records","spark":"dispatch_date","status":"status","table":"osp_jobs","title":"OSP"},
{"base":[{"col":"complaint_type","op":"eq","value":"CUSTOMER"}],"date":"complaint_date","department":"QUALITY","detail":[["Subject","subject"],["Severity","severity"],["Target","target_closure_date"]],"entry_route":"customer-complaint","icon":"📣","key":"customer_complaints","metrics":["mk_ccomp_open","mk_ccomp_overdue","mk_ccomp_rca_pending","mk_ccomp_month","mk_ccomp_closed_month","mk_ccomp_debit_pending"],"module_key":"COMPLAINT_MANAGEMENT","part":"part_id","party":["party_id"],"ref":["complaint_number"],"route":"customer-complaint-register","spark":"complaint_date","status":"status","table":"quality_complaints","title":"Customer complaints"},
{"base":[{"col":"complaint_type","op":"eq","value":"SUPPLIER"}],"date":"complaint_date","department":"QUALITY","detail":[["Subject","subject"],["Severity","severity"],["Target","target_closure_date"]],"entry_route":"supplier-complaint","icon":"🏭","key":"supplier_complaints","metrics":["mk_scomp_open","mk_scomp_overdue","mk_scomp_rca_pending","mk_scomp_month","mk_scomp_closed_month","mk_scomp_debit_pending"],"module_key":"COMPLAINT_MANAGEMENT","part":"part_id","party":["party_id"],"ref":["complaint_number"],"route":"supplier-complaint-register","spark":"complaint_date","status":"status","table":"quality_complaints","title":"Supplier complaints"},
{"base":[{"any":[{"col":"status","op":"blank"},{"col":"status","op":"eq","value":"ACTIVE"}]}],"date":"next_due_date","department":"QUALITY","detail":[["","asset_name"],["Type","asset_type"],["Calibration due","next_due_date"],["Validation due","next_validation_due_date"]],"entry_route":"calibration-validation","icon":"📏","key":"calibration","metrics":["mk_cal_overdue","mk_cal_due_30","mk_cal_done_month","mk_cal_active"],"module_key":"CALIBRATION_VALIDATION","part":"","party":[],"ref":["asset_code","asset_number"],"route":"calibration-validation","spark":"last_calibration_date","status":"status","table":"quality_assets","title":"Calibration & validation"},
{"base":[],"date":"inspection_date","department":"QUALITY","detail":[["","instrument_type"],["Heat","heat_number"],["Batch","batch_code"]],"entry_route":"standard-room-inspection","icon":"🎯","key":"standard_room","metrics":["mk_std_pending","mk_std_month","mk_std_pass_month","mk_std_fail_month"],"module_key":"CALIBRATION_VALIDATION","part":"part_id","party":[],"ref":["report_number","batch_code"],"route":"standard-room-inspection","spark":"inspection_date","status":"inspection_status","table":"standard_room_inspection_records","title":"Standard room"},
{"base":[],"date":"calculation_date","department":"QUALITY","detail":[["","calculation_type"],["Heat","heat_number"],["Result","result_value"]],"entry_route":"qc-tools","icon":"🧮","key":"qc_calc","metrics":["mk_qc_today","mk_qc_month","mk_qc_last_month","mk_qc_all"],"module_key":"QC_CALCULATION_TOOLS","part":"part_id","party":[],"ref":["calculation_number"],"route":"qc-calculation-records","spark":"calculation_date","status":"status","table":"qc_calculation_records","title":"QC calculations"},
{"base":[],"date":"customer_delivery_date","department":"SUPPLY_CHAIN","detail":[["Order","customer_order_no"],["Qty","order_qty_pcs"],["Type","order_type"]],"entry_route":"supply-customer-orders","icon":"🧾","key":"customer_orders","metrics":["mk_co_open","mk_co_overdue","mk_co_due_7","mk_co_rm_needed","mk_co_month","mk_co_completed_month"],"module_key":"SUPPLY_CHAIN","part":"part_id","party":["customer_id"],"ref":["master_reference_no","customer_order_no"],"route":"supply-customer-orders","spark":"order_date","status":"status","table":"supply_customer_orders","title":"Customer orders"},
{"base":[],"date":"order_date","department":"SUPPLY_CHAIN","detail":[["Type","po_type"],["Delivery","delivery_date"],["Total","grand_total"],["Approval","approval_status"]],"entry_route":"supply-purchase-orders","icon":"📑","key":"purchase_orders","metrics":["mk_po_pending_approval","mk_po_approval_old","mk_po_open","mk_po_overdue","mk_po_approved_month"],"module_key":"SUPPLY_CHAIN","part":"","party":["supplier_id"],"ref":["po_number"],"route":"supply-po-order-list","spark":"order_date","status":"status","table":"supply_purchase_orders","title":"Purchase orders"},
{"base":[],"date":"requested_at","department":"SUPPLY_CHAIN","detail":[["Priority","priority"],["Reminders","reminder_count"]],"entry_route":"","icon":"📨","key":"po_confirmations","metrics":["mk_poc_pending","mk_poc_old","mk_poc_confirmed_month"],"module_key":"SUPPLY_CHAIN","part":"","party":["supplier_id"],"ref":["confirmation_reference"],"route":"supply-po-order-list","spark":"created_at","status":"confirmation_status","table":"supply_po_confirmations","title":"PO confirmations"},
{"base":[],"date":"order_date","department":"SUPPLY_CHAIN","detail":[["Qty kg","ordered_qty_kg"],["Expected","expected_date"]],"entry_route":"supply-rm-procurement","icon":"🛒","key":"rm_procurement","metrics":["mk_rmpo_open","mk_rmpo_overdue","mk_rmpo_month"],"module_key":"SUPPLY_CHAIN","part":"","party":["rm_supplier_id"],"ref":["supplier_order_no"],"route":"supply-rm-procurement","spark":"order_date","status":"status","table":"supply_rm_purchase_orders","title":"RM procurement"},
{"base":[],"date":"receipt_date","department":"SUPPLY_CHAIN","detail":[["Heat","heat_number"],["Qty kg","received_qty_kg"],["Challan","supplier_challan"]],"entry_route":"supply-rm-receipt","icon":"🚚","key":"rm_receipt","metrics":["mk_rmr_month","mk_rmr_last_month","mk_rmr_no_inward"],"module_key":"SUPPLY_CHAIN","part":"","party":[],"ref":["receipt_number"],"route":"supply-rm-receipt","spark":"receipt_date","status":"","table":"supply_rm_receipts","title":"RM receipt"},
{"base":[],"date":"dispatch_date","department":"SUPPLY_CHAIN","detail":[["Heat","heat_number"],["Qty kg","qty_kg"],["Challan","challan_number"]],"entry_route":"supply-rm-dispatch","icon":"🔁","key":"rm_dispatch","metrics":["mk_rmd_month","mk_rmd_last_month","mk_rmd_all"],"module_key":"SUPPLY_CHAIN","part":"","party":["forging_supplier_id"],"ref":["dispatch_number","challan_number"],"route":"supply-rm-dispatch","spark":"dispatch_date","status":"","table":"supply_rm_dispatches","title":"RM to forging"},
{"base":[],"date":"order_date","department":"SUPPLY_CHAIN","detail":[["Qty","order_qty_pcs"],["Heat","heat_number"],["Expected","expected_date"]],"entry_route":"supply-forging","icon":"🔨","key":"forging","metrics":["mk_fo_open","mk_fo_overdue","mk_fo_approval","mk_fo_month"],"module_key":"SUPPLY_CHAIN","part":"","party":["forging_supplier_id"],"ref":["supplier_order_no"],"route":"supply-forging","spark":"order_date","status":"status","table":"supply_forging_orders","title":"Forging"},
{"base":[],"date":"event_date","department":"SUPPLY_CHAIN","detail":[["Qty","qty_pcs"],["Rejected","rejected_qty_pcs"],["Heat","heat_number"],["Invoice","invoice_no"]],"entry_route":"supply-downstream","icon":"🏁","key":"dispatch","metrics":["mk_ds_machining_month","mk_ds_fg_month","mk_ds_dispatch_month","mk_ds_rejections_month"],"module_key":"SUPPLY_CHAIN","part":"","party":[],"ref":["reference_no","invoice_no"],"route":"supply-downstream","spark":"event_date","status":"event_type","table":"supply_downstream_events","title":"Production / dispatch"},
{"base":[],"date":"created_at","department":"SUPPLY_CHAIN","detail":[["Heat","heat_number"],["Available pcs","available_quantity_pcs"],["kg","quantity_kg"],["Location","stock_location"]],"entry_route":"supply-opening-stock","icon":"🗃️","key":"opening_stock","metrics":["mk_os_available","mk_os_fg","mk_os_all"],"module_key":"SUPPLY_CHAIN","part":"part_id","party":["supplier_id"],"ref":["lot_reference","heat_number"],"route":"supply-opening-stock","spark":"created_at","status":"stage","table":"supply_opening_stock","title":"Opening stock"},
{"base":[],"date":"po_date","department":"SUPPLY_CHAIN","detail":[["Dept","department"],["Delivery","delivery_date"],["Total","grand_total"]],"entry_route":"indirect-po","icon":"🧰","key":"indirect_po","metrics":["mk_ipo_pending_approval","mk_ipo_open","mk_ipo_overdue","mk_ipo_draft","mk_ipo_month"],"module_key":"SUPPLY_CHAIN","part":"","party":["supplier_id"],"ref":["po_number"],"route":"indirect-po-list","spark":"po_date","status":"status","table":"indirect_purchase_orders","title":"Indirect purchase"},
{"base":[],"date":"pr_date","department":"SUPPLY_CHAIN","detail":[["Dept","department"],["Purpose","purpose"],["Required","required_date"]],"entry_route":"indirect-requisition","icon":"📝","key":"indirect_pr","metrics":["mk_ipr_pending","mk_ipr_to_order","mk_ipr_month"],"module_key":"SUPPLY_CHAIN","part":"","party":[],"ref":["pr_number"],"route":"indirect-requisition","spark":"pr_date","status":"status","table":"indirect_purchase_requisitions","title":"Indirect requisitions"},
{"base":[],"date":"dispatch_date","department":"PRODUCTION","detail":[["Challan","dispatch_challan"],["Qty","quantity_dispatched"],["Return","expected_return_date"]],"entry_route":"","icon":"⚙️","key":"production_osp","metrics":["mk_posp_at_vendor","mk_posp_overdue","mk_posp_dispatched_month","mk_posp_released_month"],"module_key":"OSP_TRANSACTIONS","part":"part_id","party":["vendor_id"],"ref":["osp_job_number","dispatch_challan"],"route":"osp-records","spark":"dispatch_date","status":"status","table":"osp_jobs","title":"OSP & release"},
{"base":[],"date":"delivery_date","department":"NPD","detail":[["Qty","order_qty"],["Delivery","delivery_date"]],"entry_route":"npd-status","icon":"🧭","key":"npd_orders","metrics":["mk_npd_open","mk_npd_late","mk_npd_in_progress","mk_npd_completed_month"],"module_key":"NPD_APQP","part":"part_id","party":["customer_id"],"ref":["order_number"],"route":"npd-status","spark":"order_date","status":"status","table":"npd_orders","title":"NPD orders"},
{"base":[],"date":"target_date","department":"NPD","detail":[["Op","operation_no"],["Responsible","responsible"]],"entry_route":"","icon":"🪜","key":"npd_steps","metrics":["mk_nps_open","mk_nps_overdue","mk_nps_due_7","mk_nps_done_month"],"module_key":"NPD_APQP","part":"","party":[],"ref":["process_name_snapshot","process_name"],"route":"npd-status","spark":"completed_date","status":"status","table":"npd_order_steps","title":"NPD steps"},
{"base":[],"date":"target_submission_date","department":"NPD","detail":[["Level","submission_level"],["Done %","completion_percent"],["Coordinator","coordinator"]],"entry_route":"apqp","icon":"📋","key":"apqp","metrics":["mk_apqp_active","mk_apqp_late","mk_apqp_approved_month"],"module_key":"NPD_APQP","part":"part_id","party":["customer_id"],"ref":["project_code"],"route":"apqp","spark":"created_at","status":"status","table":"ppap_projects","title":"APQP / PPAP"},
{"base":[],"date":"created_at","department":"MASTERS","detail":[["","part_name"],["Drawing","drawing_number"],["FSI","fsi_part_number"]],"entry_route":"part-entry","icon":"⚙","key":"parts_master","metrics":["mk_parts_no_layout","mk_parts_inactive","mk_parts_no_drawing","mk_parts_no_grade","mk_parts_no_customer","mk_parts_no_weight"],"module_key":"PART_MASTER","part":"id","party":["customer_id"],"ref":["part_number"],"route":"part-records","spark":"created_at","status":"status","table":"parts","title":"Part master"},
{"base":[],"date":"created_at","department":"MASTERS","detail":[["","party_name"],["City","city"],["Approval","approval_status"]],"entry_route":"reference-entry","icon":"🤝","key":"parties_master","metrics":["mk_party_inactive","mk_party_not_approved","mk_party_no_email","mk_party_no_tax"],"module_key":"REFERENCE_MASTERS","part":"","party":["id"],"ref":["party_code"],"route":"reference-records","spark":"created_at","status":"status","table":"parties","title":"Customers / suppliers"}
],"metrics":{
"mk_metlab_pending":{"filter":[{"col":"status","op":"neq","value":"FINAL"}],"group":"metlab","label":"Pending","tone":"watch","unit":"reports"},
"mk_metlab_overdue":{"filter":[{"col":"status","op":"neq","value":"FINAL"},{"col":"created_at","op":"lt","value":{"today":-3}}],"group":"metlab","label":"Pending > 3 days","tone":"alert","unit":"reports"},
"mk_metlab_month":{"filter":[{"col":"created_at","op":"gte","value":{"month_start":0}}],"group":"metlab","label":"Created this month","tone":"info","unit":"reports"},
"mk_metlab_final_month":{"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"metlab","label":"Finalized this month","tone":"done","unit":"reports"},
"mk_metlab_reserve_month":{"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}},{"col":"disposition","op":"eq","value":"ACCEPTED_UNDER_RESERVE"}],"group":"metlab","label":"Under reserve this month","tone":"watch","unit":"reports"},
"mk_metlab_rejected_pct":{"den_filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}},{"col":"disposition","op":"in","value":["REJECTED"]}],"group":"metlab","label":"Rejected % (this month)","measure":"percent","tone":"rate","unit":"%"},
"mk_dimensional_pending":{"filter":[{"col":"status","op":"neq","value":"FINAL"}],"group":"dimensional","label":"Pending","tone":"watch","unit":"reports"},
"mk_dimensional_overdue":{"filter":[{"col":"status","op":"neq","value":"FINAL"},{"col":"created_at","op":"lt","value":{"today":-3}}],"group":"dimensional","label":"Pending > 3 days","tone":"alert","unit":"reports"},
"mk_dimensional_month":{"filter":[{"col":"created_at","op":"gte","value":{"month_start":0}}],"group":"dimensional","label":"Created this month","tone":"info","unit":"reports"},
"mk_dimensional_final_month":{"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"dimensional","label":"Finalized this month","tone":"done","unit":"reports"},
"mk_dimensional_reserve_month":{"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}},{"col":"disposition","op":"eq","value":"ACCEPTED_UNDER_RESERVE"}],"group":"dimensional","label":"Under reserve this month","tone":"watch","unit":"reports"},
"mk_dimensional_rejected_pct":{"den_filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}},{"col":"disposition","op":"in","value":["REJECTED"]}],"group":"dimensional","label":"Rejected % (this month)","measure":"percent","tone":"rate","unit":"%"},
"mk_bend_pending":{"filter":[{"col":"status","op":"neq","value":"FINAL"}],"group":"bend","label":"Pending","tone":"watch","unit":"reports"},
"mk_bend_overdue":{"filter":[{"col":"status","op":"neq","value":"FINAL"},{"col":"created_at","op":"lt","value":{"today":-3}}],"group":"bend","label":"Pending > 3 days","tone":"alert","unit":"reports"},
"mk_bend_month":{"filter":[{"col":"created_at","op":"gte","value":{"month_start":0}}],"group":"bend","label":"Created this month","tone":"info","unit":"reports"},
"mk_bend_final_month":{"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"bend","label":"Finalized this month","tone":"done","unit":"reports"},
"mk_bend_reserve_month":{"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}},{"col":"disposition","op":"eq","value":"ACCEPTED_UNDER_RESERVE"}],"group":"bend","label":"Under reserve this month","tone":"watch","unit":"reports"},
"mk_bend_rejected_pct":{"den_filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"filter":[{"col":"status","op":"eq","value":"FINAL"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}},{"col":"disposition","op":"in","value":["REJECTED"]}],"group":"bend","label":"Rejected % (this month)","measure":"percent","tone":"rate","unit":"%"},
"mk_rmtc_pending":{"filter":[{"col":"status","op":"not_in","value":["APPROVED","REJECTED","CANCELLED"]}],"group":"rmtc","label":"Pending decision","tone":"watch","unit":"certificates"},
"mk_rmtc_overdue":{"filter":[{"col":"status","op":"not_in","value":["APPROVED","REJECTED","CANCELLED"]},{"col":"created_at","op":"lt","value":{"today":-7}}],"group":"rmtc","label":"Pending > 7 days","tone":"alert","unit":"certificates"},
"mk_rmtc_approval":{"filter":[{"col":"status","op":"eq","value":"APPROVAL_PENDING"}],"group":"rmtc","label":"Awaiting approval","tone":"watch","unit":"certificates"},
"mk_rmtc_approved_month":{"filter":[{"col":"status","op":"eq","value":"APPROVED"},{"col":["decision_at","approved_at","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"rmtc","label":"Approved this month","tone":"done","unit":"certificates"},
"mk_rmtc_reserve":{"filter":[{"col":"disposition","op":"eq","value":"ACCEPTED_UNDER_RESERVE"}],"group":"rmtc","label":"Accepted under reserve","tone":"watch","unit":"certificates"},
"mk_rmtc_rejected_month":{"filter":[{"col":"status","op":"eq","value":"REJECTED"},{"col":["decision_at","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"rmtc","label":"Rejected this month","tone":"alert","unit":"certificates"},
"mk_inward_hold":{"filter":[{"col":"status","op":"eq","value":"HOLD_PENDING_INSPECTION"}],"group":"inward","label":"On quality hold","tone":"watch","unit":"lots"},
"mk_inward_hold_old":{"filter":[{"col":"status","op":"eq","value":"HOLD_PENDING_INSPECTION"},{"col":["inward_date","created_at"],"op":"lt","value":{"today":-7}}],"group":"inward","label":"On hold > 7 days","tone":"alert","unit":"lots"},
"mk_inward_month":{"filter":[{"col":["inward_date","created_at"],"op":"gte","value":{"month_start":0}}],"group":"inward","label":"Received this month","tone":"info","unit":"lots"},
"mk_inward_released_month":{"filter":[{"col":"status","op":"eq","value":"RELEASED"},{"col":["released_at","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"inward","label":"Released this month","tone":"done","unit":"lots"},
"mk_inward_reserve":{"filter":[{"col":"status","op":"eq","value":"RELEASED"},{"col":"quality_disposition","op":"eq","value":"ACCEPTED_UNDER_RESERVE"}],"group":"inward","label":"Released under reserve","tone":"watch","unit":"lots"},
"mk_osp_at_vendor":{"filter":[{"col":"status","op":"eq","value":"AT_VENDOR"}],"group":"osp","label":"At vendor","tone":"info","unit":"jobs"},
"mk_osp_overdue":{"filter":[{"col":"status","op":"eq","value":"AT_VENDOR"},{"col":"expected_return_date","op":"lt","value":{"today":0}}],"group":"osp","label":"Past return date","tone":"alert","unit":"jobs"},
"mk_osp_sample":{"filter":[{"col":"sample_received_date","op":"not_blank"},{"col":"sample_gate_status","op":"in","value":["PENDING","ON_HOLD"]}],"group":"osp","label":"Sample gate pending","tone":"watch","unit":"jobs"},
"mk_osp_receipt_qc":{"filter":[{"col":"quantity_received","op":"gt","value":0},{"col":"receipt_quality_disposition","op":"in","value":["PENDING","ON_HOLD"]}],"group":"osp","label":"Receipt QC pending","tone":"watch","unit":"jobs"},
"mk_osp_completed_month":{"filter":[{"col":"status","op":"eq","value":"COMPLETED"},{"col":["receipt_date","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"osp","label":"Released this month","tone":"done","unit":"jobs"},
"mk_osp_rejected":{"filter":[{"col":"status","op":"eq","value":"REJECTED"}],"group":"osp","label":"Rejected","tone":"alert","unit":"jobs"},
"mk_ccomp_open":{"filter":[{"col":"status","op":"not_in","value":["CLOSED","CANCELLED"]}],"group":"customer_complaints","label":"Open","tone":"watch","unit":"complaints"},
"mk_ccomp_overdue":{"filter":[{"col":"status","op":"not_in","value":["CLOSED","CANCELLED"]},{"col":"target_closure_date","op":"lt","value":{"today":0}}],"group":"customer_complaints","label":"Past target closure","tone":"alert","unit":"complaints"},
"mk_ccomp_rca_pending":{"filter":[{"col":"status","op":"not_in","value":["CLOSED","CANCELLED"]},{"col":"root_cause_confirmed","op":"not_true"}],"group":"customer_complaints","label":"Root cause not confirmed","tone":"watch","unit":"complaints"},
"mk_ccomp_month":{"filter":[{"col":"complaint_date","op":"gte","value":{"month_start":0}}],"group":"customer_complaints","label":"Received this month","tone":"info","unit":"complaints"},
"mk_ccomp_closed_month":{"filter":[{"col":"status","op":"eq","value":"CLOSED"},{"col":"closure_date","op":"gte","value":{"month_start":0}}],"group":"customer_complaints","label":"Closed this month","tone":"done","unit":"complaints"},
"mk_ccomp_debit_pending":{"filter":[{"col":"debit_note_required","op":"true"},{"col":"debit_note_status","op":"not_in","value":["SETTLED","WAIVED"]}],"group":"customer_complaints","label":"Debit note pending","tone":"watch","unit":"complaints"},
"mk_scomp_open":{"filter":[{"col":"status","op":"not_in","value":["CLOSED","CANCELLED"]}],"group":"supplier_complaints","label":"Open","tone":"watch","unit":"complaints"},
"mk_scomp_overdue":{"filter":[{"col":"status","op":"not_in","value":["CLOSED","CANCELLED"]},{"col":"target_closure_date","op":"lt","value":{"today":0}}],"group":"supplier_complaints","label":"Past target closure","tone":"alert","unit":"complaints"},
"mk_scomp_rca_pending":{"filter":[{"col":"status","op":"not_in","value":["CLOSED","CANCELLED"]},{"col":"root_cause_confirmed","op":"not_true"}],"group":"supplier_complaints","label":"Root cause not confirmed","tone":"watch","unit":"complaints"},
"mk_scomp_month":{"filter":[{"col":"complaint_date","op":"gte","value":{"month_start":0}}],"group":"supplier_complaints","label":"Received this month","tone":"info","unit":"complaints"},
"mk_scomp_closed_month":{"filter":[{"col":"status","op":"eq","value":"CLOSED"},{"col":"closure_date","op":"gte","value":{"month_start":0}}],"group":"supplier_complaints","label":"Closed this month","tone":"done","unit":"complaints"},
"mk_scomp_debit_pending":{"filter":[{"col":"debit_note_required","op":"true"},{"col":"debit_note_status","op":"not_in","value":["SETTLED","WAIVED"]}],"group":"supplier_complaints","label":"Debit note pending","tone":"watch","unit":"complaints"},
"mk_cal_overdue":{"filter":[{"any":[{"col":"next_due_date","op":"lt","value":{"today":0}},{"col":"next_validation_due_date","op":"lt","value":{"today":0}}]}],"group":"calibration","label":"Overdue","tone":"alert","unit":"assets"},
"mk_cal_due_30":{"filter":[{"not":{"any":[{"col":"next_due_date","op":"lt","value":{"today":0}},{"col":"next_validation_due_date","op":"lt","value":{"today":0}}]}},{"any":[{"col":"next_due_date","op":"lte","value":{"today":30}},{"col":"next_validation_due_date","op":"lte","value":{"today":30}}]}],"group":"calibration","label":"Due in 30 days","tone":"watch","unit":"assets"},
"mk_cal_done_month":{"filter":[{"any":[{"col":"last_calibration_date","op":"gte","value":{"month_start":0}},{"col":"last_validation_date","op":"gte","value":{"month_start":0}}]}],"group":"calibration","label":"Serviced this month","tone":"done","unit":"assets"},
"mk_cal_active":{"filter":[],"group":"calibration","label":"Active gauges / instruments","tone":"info","unit":"assets"},
"mk_std_pending":{"filter":[{"col":"inspection_status","op":"in","value":["PENDING","HOLD"]}],"group":"standard_room","label":"Pending / hold","tone":"watch","unit":"inspections"},
"mk_std_month":{"filter":[{"col":"inspection_date","op":"gte","value":{"month_start":0}}],"group":"standard_room","label":"Inspected this month","tone":"info","unit":"inspections"},
"mk_std_pass_month":{"filter":[{"col":"inspection_status","op":"eq","value":"PASS"},{"col":"inspection_date","op":"gte","value":{"month_start":0}}],"group":"standard_room","label":"Pass this month","tone":"done","unit":"inspections"},
"mk_std_fail_month":{"filter":[{"col":"inspection_status","op":"eq","value":"FAIL"},{"col":"inspection_date","op":"gte","value":{"month_start":0}}],"group":"standard_room","label":"Fail this month","tone":"alert","unit":"inspections"},
"mk_qc_today":{"filter":[{"col":"calculation_date","op":"gte","value":{"today":0}}],"group":"qc_calc","label":"Today","tone":"info","unit":"records"},
"mk_qc_month":{"filter":[{"col":"calculation_date","op":"gte","value":{"month_start":0}}],"group":"qc_calc","label":"This month","tone":"info","unit":"records"},
"mk_qc_last_month":{"filter":[{"col":"calculation_date","op":"gte","value":{"month_start":-1}},{"col":"calculation_date","op":"lt","value":{"month_start":0}}],"group":"qc_calc","label":"Last month","tone":"info","unit":"records"},
"mk_qc_all":{"filter":[],"group":"qc_calc","label":"All saved","tone":"info","unit":"records"},
"mk_co_open":{"filter":[{"col":"status","op":"in","value":["OPEN","IN_PROGRESS"]}],"group":"customer_orders","label":"Open orders","tone":"info","unit":"orders"},
"mk_co_overdue":{"filter":[{"col":"status","op":"in","value":["OPEN","IN_PROGRESS"]},{"col":"customer_delivery_date","op":"lt","value":{"today":0}}],"group":"customer_orders","label":"Past delivery date","tone":"alert","unit":"orders"},
"mk_co_due_7":{"filter":[{"col":"status","op":"in","value":["OPEN","IN_PROGRESS"]},{"col":"customer_delivery_date","op":"gte","value":{"today":0}},{"col":"customer_delivery_date","op":"lte","value":{"today":7}}],"group":"customer_orders","label":"Due in 7 days","tone":"watch","unit":"orders"},
"mk_co_rm_needed":{"filter":[{"col":"status","op":"in","value":["OPEN","IN_PROGRESS"]},{"col":"rm_procurement_required","op":"true"}],"group":"customer_orders","label":"RM procurement required","tone":"watch","unit":"orders"},
"mk_co_month":{"filter":[{"col":["order_date","created_at"],"op":"gte","value":{"month_start":0}}],"group":"customer_orders","label":"Received this month","tone":"info","unit":"orders"},
"mk_co_completed_month":{"filter":[{"col":"status","op":"in","value":["COMPLETED","CLOSED"]},{"col":"updated_at","op":"gte","value":{"month_start":0}}],"group":"customer_orders","label":"Completed this month","tone":"done","unit":"orders"},
"mk_po_pending_approval":{"filter":[{"col":"approval_status","op":"eq","value":"PENDING_APPROVAL"}],"group":"purchase_orders","label":"Pending approval","tone":"watch","unit":"POs"},
"mk_po_approval_old":{"filter":[{"col":"approval_status","op":"eq","value":"PENDING_APPROVAL"},{"col":["submitted_at","created_at"],"op":"lt","value":{"today":-2}}],"group":"purchase_orders","label":"Approval waiting > 2 days","tone":"alert","unit":"POs"},
"mk_po_open":{"filter":[{"col":"status","op":"in","value":["OPEN","PARTIAL"]}],"group":"purchase_orders","label":"Open / partial","tone":"info","unit":"POs"},
"mk_po_overdue":{"filter":[{"col":"status","op":"in","value":["OPEN","PARTIAL"]},{"col":"delivery_date","op":"lt","value":{"today":0}}],"group":"purchase_orders","label":"Past delivery date","tone":"alert","unit":"POs"},
"mk_po_approved_month":{"filter":[{"col":"approval_status","op":"eq","value":"APPROVED"},{"col":"approved_at","op":"gte","value":{"month_start":0}}],"group":"purchase_orders","label":"Approved this month","tone":"done","unit":"POs"},
"mk_poc_pending":{"filter":[{"col":"confirmation_status","op":"eq","value":"PENDING"}],"group":"po_confirmations","label":"Awaiting supplier","tone":"watch","unit":"POs"},
"mk_poc_old":{"filter":[{"col":"confirmation_status","op":"eq","value":"PENDING"},{"col":["requested_at","created_at"],"op":"lt","value":{"today":-3}}],"group":"po_confirmations","label":"Waiting > 3 days","tone":"alert","unit":"POs"},
"mk_poc_confirmed_month":{"filter":[{"col":"confirmation_status","op":"eq","value":"CONFIRMED"},{"col":"confirmed_at","op":"gte","value":{"month_start":0}}],"group":"po_confirmations","label":"Confirmed this month","tone":"done","unit":"POs"},
"mk_rmpo_open":{"filter":[{"col":"status","op":"eq","value":"OPEN"}],"group":"rm_procurement","label":"RM orders open","tone":"info","unit":"orders"},
"mk_rmpo_overdue":{"filter":[{"col":"status","op":"eq","value":"OPEN"},{"col":"expected_date","op":"lt","value":{"today":0}}],"group":"rm_procurement","label":"Past expected date","tone":"alert","unit":"orders"},
"mk_rmpo_month":{"filter":[{"col":"order_date","op":"gte","value":{"month_start":0}}],"group":"rm_procurement","label":"Ordered this month","tone":"info","unit":"orders"},
"mk_rmr_month":{"filter":[{"col":"receipt_date","op":"gte","value":{"month_start":0}}],"group":"rm_receipt","label":"Received this month","tone":"info","unit":"receipts"},
"mk_rmr_last_month":{"filter":[{"col":"receipt_date","op":"gte","value":{"month_start":-1}},{"col":"receipt_date","op":"lt","value":{"month_start":0}}],"group":"rm_receipt","label":"Last month","tone":"info","unit":"receipts"},
"mk_rmr_no_inward":{"filter":[{"col":"inward_lot_id","op":"blank"}],"group":"rm_receipt","label":"Not linked to inward","tone":"watch","unit":"receipts"},
"mk_rmd_month":{"filter":[{"col":"dispatch_date","op":"gte","value":{"month_start":0}}],"group":"rm_dispatch","label":"Dispatched this month","tone":"info","unit":"dispatches"},
"mk_rmd_last_month":{"filter":[{"col":"dispatch_date","op":"gte","value":{"month_start":-1}},{"col":"dispatch_date","op":"lt","value":{"month_start":0}}],"group":"rm_dispatch","label":"Last month","tone":"info","unit":"dispatches"},
"mk_rmd_all":{"filter":[],"group":"rm_dispatch","label":"All dispatches","tone":"info","unit":"dispatches"},
"mk_fo_open":{"filter":[{"col":"status","op":"eq","value":"OPEN"}],"group":"forging","label":"Orders open","tone":"info","unit":"orders"},
"mk_fo_overdue":{"filter":[{"col":"status","op":"eq","value":"OPEN"},{"col":"expected_date","op":"lt","value":{"today":0}}],"group":"forging","label":"Past expected date","tone":"alert","unit":"orders"},
"mk_fo_approval":{"filter":[{"col":"status","op":"eq","value":"PENDING_APPROVAL"}],"group":"forging","label":"Pending approval","tone":"watch","unit":"orders"},
"mk_fo_month":{"filter":[{"col":"order_date","op":"gte","value":{"month_start":0}}],"group":"forging","label":"Ordered this month","tone":"info","unit":"orders"},
"mk_ds_machining_month":{"filter":[{"col":"event_type","op":"eq","value":"MACHINING"},{"col":"event_date","op":"gte","value":{"month_start":0}}],"group":"dispatch","label":"Machining this month","tone":"info","unit":"events"},
"mk_ds_fg_month":{"filter":[{"col":"event_type","op":"eq","value":"FINISHED_GOODS"},{"col":"event_date","op":"gte","value":{"month_start":0}}],"group":"dispatch","label":"Finished goods this month","tone":"info","unit":"events"},
"mk_ds_dispatch_month":{"filter":[{"col":"event_type","op":"eq","value":"CUSTOMER_DISPATCH"},{"col":"event_date","op":"gte","value":{"month_start":0}}],"group":"dispatch","label":"Customer dispatch this month","tone":"done","unit":"events"},
"mk_ds_rejections_month":{"filter":[{"col":"rejected_qty_pcs","op":"gt","value":0},{"col":"event_date","op":"gte","value":{"month_start":0}}],"group":"dispatch","label":"With rejections this month","tone":"alert","unit":"events"},
"mk_os_available":{"filter":[{"col":"available_quantity_pcs","op":"gt","value":0}],"group":"opening_stock","label":"Lots with stock","tone":"info","unit":"lots"},
"mk_os_fg":{"filter":[{"col":"stage","op":"eq","value":"FINISHED_GOODS"}],"group":"opening_stock","label":"Finished goods lots","tone":"info","unit":"lots"},
"mk_os_all":{"filter":[],"group":"opening_stock","label":"All lots","tone":"info","unit":"lots"},
"mk_ipo_pending_approval":{"filter":[{"col":"approval_status","op":"eq","value":"PENDING_APPROVAL"}],"group":"indirect_po","label":"Pending approval","tone":"watch","unit":"POs"},
"mk_ipo_open":{"filter":[{"col":"status","op":"in","value":["APPROVED","PARTIALLY_RECEIVED"]}],"group":"indirect_po","label":"Approved / open","tone":"info","unit":"POs"},
"mk_ipo_overdue":{"filter":[{"col":"status","op":"in","value":["APPROVED","PARTIALLY_RECEIVED"]},{"col":"delivery_date","op":"lt","value":{"today":0}}],"group":"indirect_po","label":"Past delivery date","tone":"alert","unit":"POs"},
"mk_ipo_draft":{"filter":[{"col":"status","op":"eq","value":"DRAFT"}],"group":"indirect_po","label":"Draft","tone":"info","unit":"POs"},
"mk_ipo_month":{"filter":[{"col":"po_date","op":"gte","value":{"month_start":0}}],"group":"indirect_po","label":"Raised this month","tone":"info","unit":"POs"},
"mk_ipr_pending":{"filter":[{"col":"status","op":"in","value":["SUBMITTED","PENDING_APPROVAL"]}],"group":"indirect_pr","label":"Awaiting approval","tone":"watch","unit":"requisitions"},
"mk_ipr_to_order":{"filter":[{"col":"status","op":"eq","value":"APPROVED"},{"col":"converted_po_id","op":"blank"}],"group":"indirect_pr","label":"Approved, PO not raised","tone":"watch","unit":"requisitions"},
"mk_ipr_month":{"filter":[{"col":"pr_date","op":"gte","value":{"month_start":0}}],"group":"indirect_pr","label":"Raised this month","tone":"info","unit":"requisitions"},
"mk_posp_at_vendor":{"filter":[{"col":"status","op":"eq","value":"AT_VENDOR"}],"group":"production_osp","label":"At vendor","tone":"info","unit":"jobs"},
"mk_posp_overdue":{"filter":[{"col":"status","op":"eq","value":"AT_VENDOR"},{"col":"expected_return_date","op":"lt","value":{"today":0}}],"group":"production_osp","label":"Past return date","tone":"alert","unit":"jobs"},
"mk_posp_dispatched_month":{"filter":[{"col":"dispatch_date","op":"gte","value":{"month_start":0}}],"group":"production_osp","label":"Sent this month","tone":"info","unit":"jobs"},
"mk_posp_released_month":{"filter":[{"col":"status","op":"eq","value":"COMPLETED"},{"col":["receipt_date","updated_at"],"op":"gte","value":{"month_start":0}}],"group":"production_osp","label":"Released this month","tone":"done","unit":"jobs"},
"mk_npd_open":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","CLOSED","CANCELLED"]}],"group":"npd_orders","label":"Open / in progress","tone":"info","unit":"orders"},
"mk_npd_late":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","CLOSED","CANCELLED"]},{"col":"delivery_date","op":"lt","value":{"today":0}}],"group":"npd_orders","label":"Late","tone":"alert","unit":"orders"},
"mk_npd_in_progress":{"filter":[{"col":"status","op":"eq","value":"IN_PROGRESS"}],"group":"npd_orders","label":"In progress","tone":"info","unit":"orders"},
"mk_npd_completed_month":{"filter":[{"col":"status","op":"in","value":["COMPLETED","CLOSED"]},{"col":"updated_at","op":"gte","value":{"month_start":0}}],"group":"npd_orders","label":"Completed this month","tone":"done","unit":"orders"},
"mk_nps_open":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","DONE","CLOSED","CANCELLED"]}],"group":"npd_steps","label":"Steps open","tone":"info","unit":"steps"},
"mk_nps_overdue":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","DONE","CLOSED","CANCELLED"]},{"col":"target_date","op":"lt","value":{"today":0}}],"group":"npd_steps","label":"Overdue","tone":"alert","unit":"steps"},
"mk_nps_due_7":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","DONE","CLOSED","CANCELLED"]},{"col":"target_date","op":"gte","value":{"today":0}},{"col":"target_date","op":"lte","value":{"today":7}}],"group":"npd_steps","label":"Due in 7 days","tone":"watch","unit":"steps"},
"mk_nps_done_month":{"filter":[{"col":"status","op":"in","value":["COMPLETED","DONE"]},{"col":"completed_date","op":"gte","value":{"month_start":0}}],"group":"npd_steps","label":"Completed this month","tone":"done","unit":"steps"},
"mk_apqp_active":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","CLOSED","CANCELLED","APPROVED"]}],"group":"apqp","label":"Active projects","tone":"info","unit":"projects"},
"mk_apqp_late":{"filter":[{"col":"status","op":"not_in","value":["COMPLETED","CLOSED","CANCELLED","APPROVED"]},{"col":"target_submission_date","op":"lt","value":{"today":0}}],"group":"apqp","label":"Past target submission","tone":"alert","unit":"projects"},
"mk_apqp_approved_month":{"filter":[{"col":"status","op":"in","value":["COMPLETED","APPROVED"]},{"col":"updated_at","op":"gte","value":{"month_start":0}}],"group":"apqp","label":"Approved this month","tone":"done","unit":"projects"},
"mk_parts_no_layout":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"not_exists":{"fk":"part_id","table":"inspection_plans","where":[{"col":"status","op":"eq","value":"APPROVED"}]}}],"group":"parts_master","label":"Active parts without layout","tone":"watch","unit":"parts"},
"mk_parts_inactive":{"filter":[{"col":"status","op":"neq","value":"ACTIVE"}],"group":"parts_master","label":"Inactive parts","tone":"info","unit":"parts"},
"mk_parts_no_drawing":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"col":"drawing_number","op":"blank"}],"group":"parts_master","label":"Missing drawing number","tone":"watch","unit":"parts"},
"mk_parts_no_grade":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"col":"material_grade_id","op":"blank"}],"group":"parts_master","label":"Missing material grade","tone":"watch","unit":"parts"},
"mk_parts_no_customer":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"col":"customer_id","op":"blank"}],"group":"parts_master","label":"Missing customer","tone":"watch","unit":"parts"},
"mk_parts_no_weight":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"col":"forging_weight_kg","op":"blank"}],"group":"parts_master","label":"Missing forging weight","tone":"watch","unit":"parts"},
"mk_party_inactive":{"filter":[{"col":"status","op":"neq","value":"ACTIVE"}],"group":"parties_master","label":"Inactive","tone":"info","unit":"parties"},
"mk_party_not_approved":{"filter":[{"col":"approval_status","op":"neq","value":"APPROVED"}],"group":"parties_master","label":"Not approved","tone":"watch","unit":"parties"},
"mk_party_no_email":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"col":"email","op":"blank"},{"col":"notification_emails","op":"blank"}],"group":"parties_master","label":"Missing e-mail","tone":"watch","unit":"parties"},
"mk_party_no_tax":{"filter":[{"col":"status","op":"eq","value":"ACTIVE"},{"col":"tax_identifier","op":"blank"}],"group":"parties_master","label":"Missing GSTIN / tax id","tone":"watch","unit":"parties"}
},"legacy":{
"inward_hold":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Inward on quality hold"},
"inward_released":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Released heats"},
"inward_all":{"measure":"count","route":"inward-records","source":"inward_lots","title":"All material inward"},
"inward_accepted_pcs":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Inward with accepted production"},
"inward_rejected_pcs":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Inward with rejected production"},
"inward_hold_pcs":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Inward with production on hold"},
"heats_released_month":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Heats released this month"},
"rejection_180d":{"measure":"percent","route":"inward-records","source":"inward_lots","title":"Inward lots (180 days) – rejection"},
"metlab_pending":{"measure":"count","route":"metlab-records","source":"lab_tests","title":"MetLAB pending"},
"bend_pending":{"measure":"count","route":"bend-test-records","source":"lab_tests","title":"Bend Test pending"},
"dimensional_pending":{"measure":"count","route":"dimensional-records","source":"inspection_reports","title":"Dimensional pending"},
"reports_final_month":{"measure":"count","route":"records-center","source":"lab_tests+inspection_reports","title":"Reports finalized this month"},
"fpy_final_reports":{"measure":"percent","route":"records-center","source":"lab_tests+inspection_reports","title":"Final quality reports"},
"rmtc_pending":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"RMTC pending"},
"rmtc_draft":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"RMTC draft"},
"rmtc_approval_pending":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"RMTC approval pending"},
"rmtc_accepted":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"RMTC accepted"},
"rmtc_under_reserve":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"RMTC under reserve"},
"rmtc_all":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"All RMTC"},
"complaints_open":{"measure":"count","route":"complaint-records","source":"quality_complaints","title":"Complaints open"},
"calibration_overdue":{"measure":"count","route":"calibration-validation","source":"quality_assets","title":"Calibration overdue"},
"calibration_due_30":{"measure":"count","route":"calibration-validation","source":"quality_assets","title":"Calibration due ≤ 30 days"},
"customer_orders_open":{"measure":"count","route":"supply-customer-orders","source":"supply_customer_orders","title":"Open customer orders"},
"customer_order_qty_open":{"measure":"sum","route":"supply-order-mis","source":"supply_customer_orders","title":"Open order quantity"},
"po_pending_approval":{"measure":"count","route":"supply-po-approval","source":"supply_purchase_orders","title":"PO pending approval"},
"po_open":{"measure":"count","route":"supply-po-order-list","source":"supply_purchase_orders","title":"Open purchase orders"},
"po_open_value":{"measure":"sum","route":"supply-po-order-list","source":"supply_purchase_orders","title":"Open PO value"},
"rm_on_order":{"measure":"sum","route":"supply-rm-procurement","source":"supply_rm_purchase_orders","title":"RM on order"},
"rm_received_month":{"measure":"sum","route":"supply-rm-receipt","source":"supply_rm_receipts","title":"RM received this month"},
"forging_orders_open":{"measure":"count","route":"supply-forging","source":"supply_forging_orders","title":"Forging orders open"},
"dispatched_month":{"measure":"sum","route":"supply-downstream","source":"supply_downstream_events","title":"Dispatched this month"},
"machined_month":{"measure":"sum","route":"supply-downstream","source":"supply_downstream_events","title":"Machined this month"},
"fg_month":{"measure":"sum","route":"supply-downstream","source":"supply_downstream_events","title":"Finished goods this month"},
"batch_pcs_available":{"measure":"sum","route":"osp-records","source":"production_batches","title":"Batches with pieces available"},
"batches_active":{"measure":"count","route":"osp-records","source":"production_batches","title":"Active production batches"},
"osp_at_vendor":{"measure":"count","route":"osp-records","source":"osp_jobs","title":"OSP at vendor"},
"osp_sample_pending":{"measure":"count","route":"osp-sample-receipt","source":"osp_jobs","title":"OSP sample pending"},
"osp_receipt_pending":{"measure":"count","route":"osp-dimensional","source":"osp_jobs","title":"OSP receipt quality pending"},
"npd_open":{"measure":"count","route":"npd-status","source":"npd_orders","title":"NPD open"},
"npd_in_progress":{"measure":"count","route":"npd-status","source":"npd_orders","title":"NPD in progress"},
"npd_late":{"measure":"count","route":"npd-status","source":"npd_orders","title":"NPD late"},
"apqp_active":{"measure":"count","route":"apqp","source":"ppap_projects","title":"APQP / PPAP active"},
"apqp_completion":{"measure":"percent","route":"apqp","source":"ppap_projects","title":"APQP / PPAP projects"},
"npd_steps_open":{"measure":"count","route":"npd-status","source":"npd_order_steps","title":"NPD steps open"},
"npd_steps_overdue":{"measure":"count","route":"npd-status","source":"npd_order_steps","title":"NPD steps overdue"},
"mod_rmtc":{"measure":"count","route":"rmtc-records","source":"rmtc_approvals","title":"RMTC pending decision"},
"mod_inward":{"measure":"count","route":"inward-records","source":"inward_lots","title":"Material inward on quality hold"},
"mod_metlab":{"measure":"count","route":"metlab-records","source":"lab_tests","title":"MetLAB reports pending"},
"mod_bend":{"measure":"count","route":"bend-test-records","source":"lab_tests","title":"Bend Test reports pending"},
"mod_dimensional":{"measure":"count","route":"dimensional-records","source":"inspection_reports","title":"Dimensional reports pending"},
"mod_osp_dimensional":{"measure":"count","route":"osp-records","source":"inspection_reports","title":"OSP Dimensional pending"},
"mod_osp_metlab":{"measure":"count","route":"osp-records","source":"lab_tests","title":"OSP MetLAB pending"},
"mod_customer_complaints":{"measure":"count","route":"customer-complaint-register","source":"quality_complaints","title":"Customer complaints open"},
"mod_supplier_complaints":{"measure":"count","route":"supplier-complaint-register","source":"quality_complaints","title":"Supplier complaints open"},
"mod_capa":{"measure":"count","route":"complaint-analysis","source":"quality_complaint_actions","title":"CAPA actions open"},
"mod_calibration":{"measure":"count","route":"calibration-validation","source":"quality_assets","title":"Calibration / validation due ≤ 30 days"},
"mod_standard_room":{"measure":"count","route":"standard-room-inspection","source":"standard_room_inspection_records","title":"Standard room pending / hold"},
"mod_layouts":{"measure":"count","route":"inspection-layout-records","source":"inspection_plans","title":"Inspection layouts in draft / approval"},
"mod_customer_orders":{"measure":"count","route":"supply-customer-orders","source":"supply_customer_orders","title":"Open customer orders"},
"mod_customer_orders_overdue":{"measure":"count","route":"supply-customer-orders","source":"supply_customer_orders","title":"Customer orders past delivery"},
"mod_rm_procurement":{"measure":"count","route":"supply-rm-procurement","source":"supply_rm_purchase_orders","title":"RM orders open"},
"mod_po_approval":{"measure":"count","route":"supply-po-approval","source":"supply_purchase_orders","title":"PO pending approval"},
"mod_po_confirmation":{"measure":"count","route":"supply-po-order-list","source":"supply_po_confirmations","title":"PO pending supplier confirmation"},
"mod_po_open":{"measure":"count","route":"supply-po-order-list","source":"supply_purchase_orders","title":"Open purchase orders"},
"mod_rm_receipt":{"measure":"count","route":"supply-rm-receipt","source":"supply_rm_receipts","title":"RM receipts this month"},
"mod_rm_dispatch":{"measure":"count","route":"supply-rm-dispatch","source":"supply_rm_dispatches","title":"RM to forging this month"},
"mod_forging":{"measure":"count","route":"supply-forging","source":"supply_forging_orders","title":"Forging orders open"},
"mod_forging_receipts":{"measure":"count","route":"supply-forging","source":"supply_forging_receipts","title":"Forging receipts this month"},
"mod_downstream":{"measure":"count","route":"supply-downstream","source":"supply_downstream_events","title":"Machining / FG / dispatch this month"},
"mod_osp_jobs":{"measure":"count","route":"osp-records","source":"osp_jobs","title":"OSP jobs at vendor"},
"mod_indirect_po":{"measure":"count","route":"indirect-po","source":"indirect_purchase_orders","title":"Indirect purchase orders open"},
"mod_batches":{"measure":"count","route":"osp-records","source":"production_batches","title":"Active production batches"},
"mod_npd_orders":{"measure":"count","route":"npd-status","source":"npd_orders","title":"NPD orders open"},
"mod_npd_steps":{"measure":"count","route":"npd-status","source":"npd_order_steps","title":"NPD steps open"},
"mod_apqp":{"measure":"count","route":"apqp","source":"ppap_projects","title":"APQP / PPAP projects active"},
"mod_quality_reports":{"measure":"count","route":"records-center","source":"lab_tests+inspection_reports","title":"Quality reports pending"}
}}$qcmsdefs$::jsonb
$fn$;

-- 2 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_col(p_col jsonb, p_alias text default 't')
returns text language plpgsql immutable set search_path = public as $$
declare
  v_name text;
  v_bits text[];
  v_out text[] := '{}';
begin
  if p_alias !~ '^[a-z_][a-z0-9_]*$' then
    raise exception 'qcms_kpi_col: invalid alias %', p_alias;
  end if;
  if jsonb_typeof(p_col) = 'array' then
    for v_name in select jsonb_array_elements_text(p_col) loop
      v_out := v_out || public.qcms_kpi_col(to_jsonb(v_name), p_alias);
    end loop;
    return 'coalesce(' || array_to_string(v_out, ', ') || ')';
  end if;
  v_name := p_col #>> '{}';
  if v_name ~ '^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$' then
    v_bits := string_to_array(v_name, '.');
    return format('(%I.%I ->> %L)', p_alias, v_bits[1], v_bits[2]);
  elsif v_name ~ '^[a-z_][a-z0-9_]*$' then
    return format('%I.%I', p_alias, v_name);
  end if;
  raise exception 'qcms_kpi_col: invalid column %', v_name;
end $$;

-- 3 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_where(p_filter jsonb, p_alias text default 't')
returns text language plpgsql immutable set search_path = public as $$
declare
  v_parts text[] := '{}';
  v_item jsonb;
  v_spec jsonb;
  v_child text;
  v_col text;
  v_op text;
  v_sql_op text;
  v_val jsonb;
  v_rhs text;
begin
  if p_filter is null or jsonb_typeof(p_filter) = 'null' then
    return 'true';
  end if;
  if jsonb_typeof(p_filter) = 'array' then
    for v_item in select value from jsonb_array_elements(p_filter) loop
      v_parts := v_parts || public.qcms_kpi_where(v_item, p_alias);
    end loop;
    return case when cardinality(v_parts) = 0 then 'true' else '(' || array_to_string(v_parts, ' and ') || ')' end;
  end if;
  if p_filter ? 'any' then
    for v_item in select value from jsonb_array_elements(p_filter -> 'any') loop
      v_parts := v_parts || public.qcms_kpi_where(v_item, p_alias);
    end loop;
    return case when cardinality(v_parts) = 0 then 'false' else '(' || array_to_string(v_parts, ' or ') || ')' end;
  end if;
  if p_filter ? 'all' then
    return public.qcms_kpi_where(p_filter -> 'all', p_alias);
  end if;
  if p_filter ? 'not' then
    return '(not ' || public.qcms_kpi_where(p_filter -> 'not', p_alias) || ')';
  end if;
  if p_filter ? 'exists' or p_filter ? 'not_exists' then
    v_spec := coalesce(p_filter -> 'exists', p_filter -> 'not_exists');
    if coalesce(v_spec ->> 'table', '') !~ '^[a-z_][a-z0-9_]*$' or coalesce(v_spec ->> 'fk', '') !~ '^[a-z_][a-z0-9_]*$' then
      raise exception 'qcms_kpi_where: invalid exists spec';
    end if;
    v_child := p_alias || 'x';
    return format('(%s exists (select 1 from public.%I %I where %I.%I = %I.id and %s))',
                  case when p_filter ? 'not_exists' then 'not' else '' end, v_spec ->> 'table', v_child, v_child, v_spec ->> 'fk', p_alias,
                  public.qcms_kpi_where(coalesce(v_spec -> 'where', '[]'::jsonb), v_child));
  end if;

  v_col := public.qcms_kpi_col(p_filter -> 'col', p_alias);
  v_op := coalesce(p_filter ->> 'op', 'eq');
  v_val := p_filter -> 'value';
  if v_op = 'blank' then
    return format('(nullif(btrim((%s)::text), %L) is null)', v_col, '');
  elsif v_op = 'not_blank' then
    return format('(nullif(btrim((%s)::text), %L) is not null)', v_col, '');
  elsif v_op = 'true' then
    return format('coalesce(lower(btrim((%s)::text)) in (%L, %L, %L, %L), false)', v_col, 'true', 't', '1', 'yes');
  elsif v_op = 'not_true' then
    return format('(not coalesce(lower(btrim((%s)::text)) in (%L, %L, %L, %L), false))', v_col, 'true', 't', '1', 'yes');
  elsif v_op = 'in' or v_op = 'not_in' then
    v_rhs := format('%L::text[]', array(select jsonb_array_elements_text(coalesce(v_val, '[]'::jsonb)))::text);
    if v_op = 'in' then
      return format('coalesce((%s)::text = any(%s), false)', v_col, v_rhs);
    end if;
    return format('(not (coalesce((%s)::text, %L) = any(%s)))', v_col, '', v_rhs);
  end if;

  v_sql_op := case v_op when 'eq' then '=' when 'neq' then '<>' when 'lt' then '<' when 'lte' then '<='
                        when 'gt' then '>' when 'gte' then '>=' end;
  if v_sql_op is null then
    raise exception 'qcms_kpi_where: invalid operator %', v_op;
  end if;
  if jsonb_typeof(v_val) = 'object' and (v_val ? 'today' or v_val ? 'month_start') then
    v_rhs := case when v_val ? 'today' then format('(current_date + (%s)::integer)', (v_val ->> 'today')::integer)
                  else format('((date_trunc(%L, current_date) + make_interval(months => (%s)::integer))::date)', 'month', (v_val ->> 'month_start')::integer) end;
    return format('coalesce((%s)::date %s %s, false)', v_col, v_sql_op, v_rhs);
  end if;
  if jsonb_typeof(v_val) = 'number' then
    return format('coalesce((%s)::numeric %s (%L)::numeric, false)', v_col, v_sql_op, v_val::text);
  end if;
  if v_op = 'neq' then
    return format('(coalesce((%s)::text, %L) <> %L)', v_col, '', v_val #>> '{}');
  end if;
  return format('coalesce((%s)::text %s %L, false)', v_col, v_sql_op, v_val #>> '{}');
end $$;

-- 4 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_drill_spec_from(p_key text, p_defs jsonb)
returns jsonb language plpgsql immutable set search_path = public as $$
declare
  v_defs jsonb := p_defs;
  v_key text := coalesce(p_key, '');
  m jsonb := v_defs -> 'metrics' -> v_key;
  l jsonb := v_defs -> 'legacy' -> v_key;
  g jsonb;
  v_cols jsonb := '["source_table","record_id","reference","part","party","status","record_date","detail"]'::jsonb;
begin
  if m is not null then
    select value into g from jsonb_array_elements(v_defs -> 'groups') where value ->> 'key' = m ->> 'group';
    return jsonb_build_object('key', v_key, 'rpc', 'qcms_kpi_drilldown', 'args', jsonb_build_object('p_card_key', v_key),
                              'source', g -> 'table', 'filter', coalesce(g -> 'base', '[]'::jsonb) || coalesce(m -> 'filter', '[]'::jsonb),
                              'columns', v_cols, 'title', (g ->> 'title') || ' · ' || (m ->> 'label'), 'open_route', g -> 'route',
                              'measure', coalesce(m ->> 'measure', 'count'), 'count_matches', coalesce(m ->> 'measure', 'count') = 'count');
  end if;
  if l is not null then
    return jsonb_build_object('key', v_key, 'rpc', 'qcms_kpi_drilldown', 'args', jsonb_build_object('p_card_key', v_key),
                              'source', l -> 'source', 'filter', jsonb_build_object('card_key', v_key, 'server', 'qcms_kpi_base'),
                              'columns', v_cols, 'title', l -> 'title', 'open_route', l -> 'route', 'measure', l -> 'measure',
                              'count_matches', (l ->> 'measure') = 'count');
  end if;
  return '{}'::jsonb;
end $$;

create or replace function public.qcms_kpi_drill_spec(p_key text)
returns jsonb language sql immutable set search_path = public as $$
  select public.qcms_kpi_drill_spec_from(p_key, public.qcms_kpi_definitions())
$$;

-- 5 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_card_k(p_key text, p_label text, p_value numeric, p_unit text, p_tone text, p_route text)
returns jsonb language sql immutable set search_path = public as $$
  select jsonb_build_object('key', p_key, 'label', p_label, 'value', coalesce(p_value, 0), 'unit', coalesce(p_unit, ''),
                            'tone', coalesce(p_tone, 'neutral'), 'route', p_route, 'web_route', p_route,
                            'drill', public.qcms_kpi_drill_spec(p_key))
$$;

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
    'tone', coalesce(p_tone, case when coalesce(p_overdue, 0) > 0 then 'critical' when coalesce(p_value, 0) > 0 then 'warning' else 'good' end),
    'drill', public.qcms_kpi_drill_spec(p_key))
$$;

-- 6 --------------------------------------------------------------------------------------------
create or replace function public.qcms_module_kpis(p_department text default null, p_modules text[] default null)
returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
  v_defs jsonb := public.qcms_kpi_definitions();
  v_dept text := nullif(upper(btrim(coalesce(p_department, ''))), '');
  g jsonb;
  m jsonb;
  v_key text;
  v_cards jsonb;
  v_groups jsonb := '[]'::jsonb;
  v_num bigint;
  v_den bigint;
  v_value numeric;
  v_tone text;
  v_spark jsonb;
begin
  if v_dept in ('SUPPLY', 'SCM', 'SUPPLYCHAIN') then v_dept := 'SUPPLY_CHAIN'; end if;
  if v_dept in ('APQP', 'NPD_APQP') then v_dept := 'NPD'; end if;
  if v_dept = 'MASTER' then v_dept := 'MASTERS'; end if;
  for g in select value from jsonb_array_elements(v_defs -> 'groups') loop
    continue when v_dept is not null and g ->> 'department' <> v_dept;
    continue when coalesce(cardinality(p_modules), 0) > 0 and not ((g ->> 'key') = any(p_modules));
    continue when to_regclass('public.' || (g ->> 'table')) is null;  -- optional modules (e.g. indirect purchase)
    v_cards := '[]'::jsonb;
    for v_key in select jsonb_array_elements_text(g -> 'metrics') loop
      m := v_defs -> 'metrics' -> v_key;
      begin
        execute format('select count(*) from public.%I t where %s', g ->> 'table',
                       public.qcms_kpi_where(coalesce(g -> 'base', '[]'::jsonb) || coalesce(m -> 'filter', '[]'::jsonb), 't')) into v_num;
        if m ->> 'measure' = 'percent' then
          execute format('select count(*) from public.%I t where %s', g ->> 'table',
                         public.qcms_kpi_where(coalesce(g -> 'base', '[]'::jsonb) || coalesce(m -> 'den_filter', '[]'::jsonb), 't')) into v_den;
          v_value := case when v_den > 0 then round(100.0 * v_num / v_den, 1) else 0 end;
        else
          v_value := v_num;
        end if;
        v_tone := case m ->> 'tone'
                    when 'alert' then case when v_value > 0 then 'critical' else 'good' end
                    when 'watch' then case when v_value > 0 then 'warning' else 'good' end
                    when 'done' then 'good'
                    when 'rate' then case when v_value > 5 then 'critical' when v_value > 0 then 'warning' else 'good' end
                    else 'neutral' end;
        v_cards := v_cards || jsonb_build_array(jsonb_build_object(
          'key', v_key, 'label', m ->> 'label', 'value', v_value, 'unit', coalesce(m ->> 'unit', ''), 'tone', v_tone,
          'route', g ->> 'route', 'count', v_num, 'drill', public.qcms_kpi_drill_spec_from(v_key, v_defs)));
      exception when others then
        null;  -- a column missing on an older database: skip that card, keep the module
      end;
    end loop;
    begin
      execute format($q$
        select coalesce(jsonb_agg(coalesce(x.c, 0) order by gs.m), '[]'::jsonb)
          from generate_series(date_trunc('month', current_date) - interval '5 months', date_trunc('month', current_date), interval '1 month') gs(m)
          left join (select date_trunc('month', (t.%1$I)::date)::date mm, count(*) c
                       from public.%2$I t
                      where %3$s and (t.%1$I)::date >= (date_trunc('month', current_date) - interval '5 months')::date
                      group by 1) x on x.mm = gs.m::date$q$,
        g ->> 'spark', g ->> 'table', public.qcms_kpi_where(g -> 'base', 't')) into v_spark;
    exception when others then
      v_spark := '[]'::jsonb;
    end;
    v_groups := v_groups || jsonb_build_array((g - 'base') || jsonb_build_object('cards', v_cards, 'spark', coalesce(v_spark, '[]'::jsonb)));
  end loop;
  return jsonb_build_object('generated_at', now(), 'department', v_dept, 'groups', v_groups);
end $$;

-- 7 --------------------------------------------------------------------------------------------
create or replace function public.qcms_kpi_drilldown(p_card_key text, p_limit integer default 500)
returns table(source_table text, record_id uuid, reference text, part text, party text, status text, record_date date, detail text)
language plpgsql stable security invoker set search_path = public as $$
declare
  v_defs jsonb := public.qcms_kpi_definitions();
  m jsonb := v_defs -> 'metrics' -> coalesce(p_card_key, '');
  g jsonb;
  v_limit integer := greatest(1, least(coalesce(p_limit, 500), 5000));
  v_ref text;
  v_party text;
  v_detail text;
  v_part_join text := '';
  v_part text := 'null::text';
  v_party_join text := '';
  v_party_label text := 'null::text';
begin
  if m is null then
    -- start-dashboard / module-strip keys keep their R37 server filter (qcms_kpi_base)
    return query select r.source_table, r.record_id, r.reference, r.part, r.party, r.status, r.record_date, r.detail
                   from public.qcms_kpi_records(p_card_key, null, v_limit) r;
    return;
  end if;
  select value into g from jsonb_array_elements(v_defs -> 'groups') where value ->> 'key' = m ->> 'group';
  if to_regclass('public.' || (g ->> 'table')) is null then
    return;
  end if;
  select string_agg(format('nullif(btrim((t.%I)::text), %L)', x, ''), ', ') into v_ref from jsonb_array_elements_text(g -> 'ref') x;
  v_ref := 'coalesce(' || coalesce(v_ref || ', ', '') || 'left(t.id::text, 8))';
  if coalesce(g ->> 'part', '') <> '' then
    v_part_join := format(' left join public.parts p on p.id = t.%I', g ->> 'part');
    v_part := format('nullif(concat_ws(%L, p.part_number, nullif(p.part_name, %L)), %L)', ' · ', '', '');
  end if;
  select string_agg(format('t.%I', x), ', ') into v_party from jsonb_array_elements_text(g -> 'party') x;
  if v_party is not null then
    v_party_join := format(' left join public.parties pt on pt.id = coalesce(%s)', v_party);
    v_party_label := 'coalesce(pt.party_name, pt.party_code)';
  end if;
  select string_agg(format('case when nullif(btrim((t.%I)::text), %L) is null then null else btrim(%L || %L || (t.%I)::text) end',
                           d ->> 1, '', d ->> 0, ' ', d ->> 1), ', ')
    into v_detail from jsonb_array_elements(g -> 'detail') d;
  return query execute format(
    'select %L::text, t.id, %s, %s, %s, %s, (t.%I)::date, nullif(concat_ws(%L%s), %L)
       from public.%I t%s%s
      where %s
      order by (t.%I)::date desc nulls last, t.created_at desc nulls last
      limit %s',
    g ->> 'table', v_ref, v_part, v_party_label,
    case when coalesce(g ->> 'status', '') = '' then 'null::text' else format('(t.%I)::text', g ->> 'status') end, g ->> 'date', ' · ', coalesce(', ' || v_detail, ''), '',
    g ->> 'table', v_part_join, v_party_join,
    public.qcms_kpi_where(coalesce(g -> 'base', '[]'::jsonb) || coalesce(m -> 'filter', '[]'::jsonb), 't'), g ->> 'date', v_limit);
end $$;

-- 8 · grants -----------------------------------------------------------------------------------
revoke all on function public.qcms_kpi_definitions() from public, anon;
grant execute on function public.qcms_kpi_definitions() to authenticated;
revoke all on function public.qcms_kpi_col(jsonb, text) from public, anon;
grant execute on function public.qcms_kpi_col(jsonb, text) to authenticated;
revoke all on function public.qcms_kpi_where(jsonb, text) from public, anon;
grant execute on function public.qcms_kpi_where(jsonb, text) to authenticated;
revoke all on function public.qcms_kpi_drill_spec_from(text, jsonb) from public, anon;
grant execute on function public.qcms_kpi_drill_spec_from(text, jsonb) to authenticated;
revoke all on function public.qcms_kpi_drill_spec(text) from public, anon;
grant execute on function public.qcms_kpi_drill_spec(text) to authenticated;
grant execute on function public.qcms_kpi_card_k(text, text, numeric, text, text, text) to authenticated;
grant execute on function public.qcms_module_card(text, text, text, text, text, numeric, text, numeric, text, numeric, numeric, text, jsonb, text) to authenticated;
revoke all on function public.qcms_module_kpis(text, text[]) from public, anon;
grant execute on function public.qcms_module_kpis(text, text[]) to authenticated;
revoke all on function public.qcms_kpi_drilldown(text, integer) from public, anon;
grant execute on function public.qcms_kpi_drilldown(text, integer) to authenticated;

notify pgrst, 'reload schema';
