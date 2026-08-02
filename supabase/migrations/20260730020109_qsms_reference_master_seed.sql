-- Optional reference seed based on the uploaded Quality Monitoring System workbook.
-- Review codes and names before using in production. This does not create transactional data.

begin;

insert into public.parties
(id, tenant_id, party_code, party_name, party_types, country, city, status)
values
('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'C000100', 'Kessler + Co. GmbH & Co. KG', array['CUSTOMER'], 'Germany', 'Abtsgmünd', 'ACTIVE'),
('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'S000104', 'Om Forge', array['SUPPLIER','FORGING_SUPPLIER'], 'India', 'Ahmednagar', 'ACTIVE')
on conflict (tenant_id, party_code) do update
set party_name = excluded.party_name, party_types = excluded.party_types, updated_at = now();

insert into public.material_grades
(id, tenant_id, grade_code, standard, revision, status)
values
('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '16MnCr5', 'Controlled customer / material specification', '01', 'ACTIVE'),
('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '20MnCr5', 'Controlled customer / material specification', '01', 'ACTIVE')
on conflict (tenant_id, grade_code, revision) do nothing;

insert into public.material_grade_elements
(id, tenant_id, material_grade_id, element, minimum, maximum, unit)
values
('21000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'C', 0.17, 0.21, '%'),
('21000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Mn', 1.10, 1.30, '%'),
('21000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Cr', 0.50, 0.90, '%'),
('21000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'P', 0.00, 0.025, '%'),
('21000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'S', 0.00, 0.025, '%'),
('21000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Mo', 0.10, 0.25, '%'),
('21000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Ni', 0.05, 0.15, '%'),
('21000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Al', 0.02, 0.05, '%'),
('21000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Cu', 0.02, 0.05, '%')
on conflict (material_grade_id, element) do update
set minimum = excluded.minimum, maximum = excluded.maximum, updated_at = now();

insert into public.parts
(id, tenant_id, part_number, part_name, customer_id, material_grade_id, drawing_number, drawing_revision,
 finished_weight_kg, forging_weight_kg, gross_weight_kg, status)
values
('30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001',
 '71.784.3', 'Differential Spider', '10000000-0000-0000-0000-000000000001',
 '20000000-0000-0000-0000-000000000001', '71.784.3', 'N', 1.8, 2.35, 3.05, 'ACTIVE')
on conflict (tenant_id, part_number) do update
set part_name = excluded.part_name, customer_id = excluded.customer_id,
    material_grade_id = excluded.material_grade_id, drawing_revision = excluded.drawing_revision,
    updated_at = now();

insert into public.part_supplier_links
(id, tenant_id, part_id, supplier_id, supplier_part_number, approved)
values
('31000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001',
 '30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', '71.784.3', true)
on conflict (tenant_id, part_id, supplier_id, steel_mill_id) do nothing;

insert into public.processes
(id, tenant_id, process_code, process_name, process_type, special_process, cqi_standard, status)
values
('40000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'FORG', 'Forging', 'OUTSOURCED', false, null, 'ACTIVE'),
('40000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'CC', 'Case Carburizing', 'OUTSOURCED', true, 'CQI-9', 'ACTIVE'),
('40000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'QT', 'Quench & Tempering', 'OUTSOURCED', true, 'CQI-9', 'ACTIVE'),
('40000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', 'BROACH', 'Broaching', 'IN_HOUSE', false, null, 'ACTIVE'),
('40000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', 'NORM', 'Normalizing', 'OUTSOURCED', true, 'CQI-9', 'ACTIVE'),
('40000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', 'GSHAPE', 'Gear Shaping', 'OUTSOURCED', false, null, 'ACTIVE')
on conflict (tenant_id, process_code) do update
set process_name = excluded.process_name, process_type = excluded.process_type,
    special_process = excluded.special_process, cqi_standard = excluded.cqi_standard, updated_at = now();

insert into public.inspection_stages
(id, tenant_id, stage_code, stage_name, sequence_no, status)
values
('41000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'RMTC', 'RMTC Approval', 10, 'ACTIVE'),
('41000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'RM-IN', 'Incoming Raw Material Inspection', 20, 'ACTIVE'),
('41000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'SETUP', 'Setup Approval', 30, 'ACTIVE'),
('41000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', 'STAGE', 'Stage Inspection', 40, 'ACTIVE'),
('41000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', 'OSP-IN', 'OSP Receipt Inspection', 50, 'ACTIVE'),
('41000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', 'FINAL', 'Final Inspection', 60, 'ACTIVE')
on conflict (tenant_id, stage_code) do update
set stage_name = excluded.stage_name, sequence_no = excluded.sequence_no, updated_at = now();

insert into public.number_sequences (tenant_id, sequence_code, prefix, current_value, padding, reset_frequency)
values
('00000000-0000-0000-0000-000000000001', 'RMTC', 'RMTC-D9', 0, 5, 'YEARLY'),
('00000000-0000-0000-0000-000000000001', 'INWARD', 'RM-IN-D9', 0, 5, 'YEARLY'),
('00000000-0000-0000-0000-000000000001', 'OSP', 'OSP-D9', 0, 5, 'YEARLY'),
('00000000-0000-0000-0000-000000000001', 'LAB', 'MLAB-D9', 0, 5, 'YEARLY'),
('00000000-0000-0000-0000-000000000001', 'AUDIT', 'AUD-D9', 0, 5, 'YEARLY'),
('00000000-0000-0000-0000-000000000001', 'PACKAGE', 'QPK-D9', 0, 5, 'YEARLY')
on conflict (tenant_id, sequence_code) do nothing;

insert into public.standards_register
(tenant_id, standard_code, edition, document_owner, status, notes)
values
('00000000-0000-0000-0000-000000000001', 'IATF 16949', '2016', 'Management Representative', 'CURRENT', 'Maintain current sanctioned interpretations and customer-specific requirements as controlled records.'),
('00000000-0000-0000-0000-000000000001', 'APQP', '3rd Edition', 'APQP Leader', 'CURRENT', 'Licensed reference; do not reproduce proprietary checklist content in the application repository.'),
('00000000-0000-0000-0000-000000000001', 'Control Plan', '1st Edition', 'Quality Head', 'CURRENT', 'Licensed reference; maintain the controlled organizational template and revision history.')
on conflict (tenant_id, standard_code, edition) do nothing;

commit;
