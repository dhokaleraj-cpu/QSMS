-- QCMS v4.14.27 — Final Dispatch MetLAB isolation + controlled PO release template.
-- Additive / configuration only. Existing quality, RMTC, inward, PO and notification records are preserved.

begin;

-- The Part Master metallurgical requirement table is a Final Dispatch specification source only.
-- Raw Material Inward eligibility is enforced in application selection by approved Layout Master plans
-- with requirement_scope <> FINAL_METALLURGICAL.
comment on table public.part_metallurgical_requirements is
'FINAL DISPATCH METLAB ONLY. These Part Master requirements generate the Final Metallurgical customer-dispatch layout. Raw Material Inward MetLAB must use an approved Layout Master plan and must not consume this table.';

-- Controlled supplier-facing Forging Purchase Order release email requested by Purchasing.
insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,
       'FORGING_PO_CREATED',
       'SUPPLY_CHAIN',
       'Forging Purchase Order Released',
       'Forging Purchase Order {{po_number}} Released through QCMS',
       E'Dear Supplier,\n\nForging Purchase Order {{po_number}} has been released through QCMS.\nSupplier: {{supplier_name}}\nPart Number: {{part_number}}\nQuantity: {{quantity}}\nDelivery Date: {{delivery_date}}\nNext Stage: {{next_stage}}\n\nPlease send us the order confirmation in next 2-3 days with duly stamp and sign.\n\nThe controlled Purchase Order PDF and available supporting documents are attached.\n\nRegards,\nFour Star Industries Pvt Ltd\nPurchasing Team',
       true,true,true,true
from public.tenants t
on conflict(tenant_id,template_key) do update set
 module_key=excluded.module_key,
 template_name=excluded.template_name,
 subject_template=excluded.subject_template,
 body_template=excluded.body_template,
 include_generated_pdf=true,
 include_record_attachments=true,
 include_supplier=true,
 enabled=true,
 updated_at=now();

-- Keep the route active and make the business next stage explicit.
insert into public.qcms_notification_routes
(tenant_id,event_key,route_label,department,department_cc,send_to_supplier,template_key,next_stage,enabled)
select t.id,'FORGING_PO_CREATED','Forging Purchase Order released','Supply Chain',true,true,'FORGING_PO_CREATED','Forging Receipt',true
from public.tenants t
on conflict(tenant_id,event_key) do update set
 route_label=excluded.route_label,
 department=excluded.department,
 department_cc=excluded.department_cc,
 send_to_supplier=true,
 template_key='FORGING_PO_CREATED',
 next_stage='Forging Receipt',
 enabled=true,
 updated_at=now();

create or replace function public.qcms_release_schema_version() returns text
language sql immutable set search_path='pg_catalog' as $$ select '4.14.27'::text $$;
revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to authenticated,service_role;

insert into public.qcms_release_schema_state(version,build,applied_at,details)
values(
 '4.14.27',
 '41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS',
 now(),
 jsonb_build_object(
   'final_metlab_part_master_only',true,
   'raw_material_metlab_layout_master_only',true,
   'forging_po_release_template',true,
   'email_database_field_picker',true
 )
)
on conflict(version) do update set build=excluded.build,applied_at=excluded.applied_at,details=excluded.details;

commit;
