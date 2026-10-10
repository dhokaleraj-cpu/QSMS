-- QCMS R15 · Separate Bend Test Layout Master.
-- A Bend Test layout (inspection_method = 'BEND_TEST') is its own controlled scope, so a Part can
-- have one current Bend Test layout AND one current general MetLAB layout for the same
-- Part + Stage + Process + Layout Type. Re-runnable.
alter table public.inspection_plans add column if not exists inspection_method text not null default 'GENERAL';

-- Mark existing layouts that are already Bend Test layouts (plan number / name / title says BEND).
update public.inspection_plans
   set inspection_method = 'BEND_TEST', updated_at = now()
 where upper(coalesce(layout_type,'')) = 'METLAB'
   and upper(coalesce(inspection_method,'GENERAL')) <> 'BEND_TEST'
   and (upper(coalesce(plan_number,'')) like '%-BEND%' or upper(coalesce(layout_name,'')) like '%BEND TEST%' or upper(coalesce(report_title,'')) like '%BEND TEST%');

drop index if exists public.uq_qcms_inspection_plan_current_scope;
create unique index uq_qcms_inspection_plan_current_scope
  on public.inspection_plans(
    tenant_id,
    part_id,
    coalesce(process_id,'00000000-0000-0000-0000-000000000000'::uuid),
    coalesce(inspection_stage_id,'00000000-0000-0000-0000-000000000000'::uuid),
    upper(coalesce(layout_type,'DIMENSIONAL')),
    upper(coalesce(inward_type,'MATERIAL_INWARD')),
    upper(coalesce(requirement_scope,'GENERAL')),
    (case when upper(coalesce(inspection_method,'GENERAL')) = 'BEND_TEST' then 'BEND_TEST' else 'GENERAL' end)
  )
  where upper(coalesce(status,'DRAFT')) in ('DRAFT','APPROVAL_PENDING','APPROVED')
    and upper(coalesce(requirement_scope,'GENERAL')) <> 'FINAL_METALLURGICAL';

comment on index public.uq_qcms_inspection_plan_current_scope is
  'QCMS R15 one current layout per Part + Stage + Process + Layout Type + Inward Type + Requirement Scope + Inspection Method (Bend Test separate from general MetLAB).';
