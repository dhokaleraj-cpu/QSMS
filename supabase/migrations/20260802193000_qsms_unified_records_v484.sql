-- QSMS 4.8.4 — Unified records register and dashboard/inward consistency.
-- Existing records are preserved.
begin;

create or replace view public.v_qsms_inward_register
with (security_invoker=true) as
select
  i.*,
  p.part_number,
  p.part_name,
  supplier.party_code as supplier_code,
  supplier.party_name as supplier_name,
  r.rmtc_number,
  r.certificate_reference as supplier_rmtc_number,
  r.status as rmtc_status,
  r.disposition as rmtc_final_disposition,
  r.certificate_quantity as rmtc_steel_quantity_kg,
  r.normalized_heat_number,
  mill.party_name as steel_mill_name,
  grade.grade_code as material_grade,
  coalesce((
    select d.disposition
    from public.inspection_reports d
    where d.inward_lot_id=i.id and d.report_type='DIMENSIONAL'
    order by d.decision_at desc nulls last,d.updated_at desc
    limit 1
  ),'PENDING') as dimensional_report_disposition,
  coalesce((
    select l.disposition
    from public.lab_tests l
    where l.inward_lot_id=i.id and l.test_type='METLAB'
    order by l.decision_at desc nulls last,l.updated_at desc
    limit 1
  ),'PENDING') as metlab_report_disposition
from public.inward_lots i
join public.parts p on p.id=i.part_id
join public.parties supplier on supplier.id=i.supplier_id
join public.rmtc_approvals r on r.id=i.rmtc_approval_id
left join public.parties mill on mill.id=r.steel_mill_id
left join public.material_grades grade on grade.id=p.material_grade_id;

grant select on public.v_qsms_inward_register to authenticated;

commit;
