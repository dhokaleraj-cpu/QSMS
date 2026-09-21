-- QCMS v4.14.36 — Complaint email configuration, confirmation, register/reminder schedules.
-- Additive / configuration only. Existing complaints, PO, RMTC and all production data remain untouched.

insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,v.template_key,'COMPLAINT_MANAGEMENT',v.template_name,v.subject_template,v.body_template,true,true,false,true
from public.tenants t cross join (values
 ('CUSTOMER_COMPLAINT_CREATED','Customer Complaint Notification','QCMS · Customer Complaint · {{complaint_number}} · {{status}}',
  'Dear Sir / Madam,\n\nCustomer Complaint {{complaint_number}} is available in QCMS.\nCustomer: {{party_name}}\nPart: {{part_number}} · {{part_description}}\nSubject: {{subject}}\nSeverity: {{severity}}\nHeat: {{heat_number}}\nBatch: {{batch_number}}\nTarget Closure: {{target_closure_date}}\nStatus: {{status}}\n\nPlease complete the required action.\n\nRegards,\nFour Star Industries Pvt. Ltd. · QCMS'),
 ('SUPPLIER_COMPLAINT_CREATED','Supplier Complaint Notification','QCMS · Supplier Complaint · {{complaint_number}} · {{status}}',
  'Dear Sir / Madam,\n\nSupplier Complaint {{complaint_number}} is available in QCMS.\nSupplier: {{party_name}}\nPart: {{part_number}} · {{part_description}}\nSubject: {{subject}}\nSeverity: {{severity}}\nHeat: {{heat_number}}\nBatch: {{batch_number}}\nTarget Closure: {{target_closure_date}}\nStatus: {{status}}\n\nPlease complete the required action.\n\nRegards,\nFour Star Industries Pvt. Ltd. · QCMS'),
 ('COMPLAINT_FOLLOWUP_REMINDER','Complaint Follow-up Reminder','QCMS · Complaint Follow-up Reminder · {{complaint_number}}',
  'Dear {{department}},\n\nComplaint {{complaint_number}} requires follow-up.\nParty: {{party_name}}\nSubject: {{subject}}\nTarget / Follow-up Date: {{due_date}}\nStatus: {{status}}\n\nPlease update the complaint and next action in QCMS.\n\nRegards,\nQCMS'),
 ('COMPLAINT_OVERDUE_REMINDER','Complaint Closure Reminder','QCMS · Complaint Closure Reminder · {{complaint_number}}',
  'Dear {{department}},\n\nComplaint {{complaint_number}} is open / due / overdue.\nParty: {{party_name}}\nSubject: {{subject}}\nTarget Closure: {{due_date}}\nStatus: {{status}}\n\nPlease complete the pending CAPA / closure actions.\n\nRegards,\nQCMS'),
 ('COMPLAINT_CLOSED','Complaint Closure Notification','QCMS · Complaint Closed · {{complaint_number}}',
  'Dear Sir / Madam,\n\nComplaint {{complaint_number}} has been closed in QCMS after verification.\nParty: {{party_name}}\nSubject: {{subject}}\nStatus: {{status}}\n\nRegards,\nFour Star Industries Pvt. Ltd. · QCMS')
) v(template_key,template_name,subject_template,body_template)
on conflict (tenant_id,template_key) do nothing;

insert into public.qcms_notification_routes
(tenant_id,event_key,route_label,department,department_cc,send_to_supplier,template_key,next_stage,enabled)
select t.id,v.event_key,v.route_label,'Quality',true,v.external_copy,v.event_key,v.next_stage,true
from public.tenants t cross join (values
 ('CUSTOMER_COMPLAINT_CREATED','Customer complaint created / updated',false,'Containment / Root Cause / Corrective Action'),
 ('SUPPLIER_COMPLAINT_CREATED','Supplier complaint created / updated',false,'Containment / Root Cause / Corrective Action'),
 ('COMPLAINT_FOLLOWUP_REMINDER','Complaint follow-up reminder',false,'Complaint Follow-up / CAPA Update'),
 ('COMPLAINT_OVERDUE_REMINDER','Complaint closure reminder',false,'CAPA / Verification / Closure'),
 ('COMPLAINT_CLOSED','Complaint closure notification',false,'Closed')
) v(event_key,route_label,external_copy,next_stage)
on conflict (tenant_id,event_key) do nothing;

insert into public.qcms_notification_schedules
(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,recipient_departments,include_suppliers,template_key,run_every_days,export_format)
select t.id,v.schedule_key,'COMPLAINT_MANAGEMENT',v.event_key,v.schedule_label,true,8,'Asia/Kolkata',v.days_ahead,true,true,'Quality','{}'::text[],false,v.event_key,1,'PDF'
from public.tenants t cross join (values
 ('COMPLAINT_CUSTOMER_OPEN_OVERDUE','COMPLAINT_OVERDUE_REMINDER','Customer Complaint · Open / Due / Overdue',2),
 ('COMPLAINT_SUPPLIER_OPEN_OVERDUE','COMPLAINT_OVERDUE_REMINDER','Supplier Complaint · Open / Due / Overdue',2),
 ('COMPLAINT_FOLLOWUP_DUE','COMPLAINT_FOLLOWUP_REMINDER','Complaint Follow-up · Due / Overdue',1)
) v(schedule_key,event_key,schedule_label,days_ahead)
on conflict (tenant_id,schedule_key) do nothing;

comment on table public.qcms_notification_schedules is 'QCMS controlled notification schedules including Supply Chain, NPD and v4.14.36 Complaint Management reminders.';
