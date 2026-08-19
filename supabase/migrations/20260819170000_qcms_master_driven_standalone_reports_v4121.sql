-- QCMS v4.12.1 - Master-driven standalone quality reports
-- Additive only. Existing transactions, IDs, approvals, attachments and report results are preserved.

begin;

alter table public.inspection_reports
  add column if not exists customer_id uuid references public.parties(id),
  add column if not exists material_grade_id uuid references public.material_grades(id),
  add column if not exists batch_number text,
  add column if not exists supplier_reference_number text,
  add column if not exists supply_condition text,
  add column if not exists reference_text text;

alter table public.lab_tests
  add column if not exists customer_id uuid references public.parties(id),
  add column if not exists batch_number text,
  add column if not exists supplier_reference_number text,
  add column if not exists supply_condition text,
  add column if not exists reference_text text;

create index if not exists idx_inspection_reports_master_context
  on public.inspection_reports(tenant_id,part_id,customer_id,material_grade_id,inspection_scope,inspection_date desc);
create index if not exists idx_lab_tests_master_context
  on public.lab_tests(tenant_id,part_id,customer_id,material_grade_id,inspection_scope,test_date desc);

-- Customer and material grade are controlled by Part Master. This database guard
-- prevents standalone or linked reports from storing a different customer/grade.
create or replace function public.qcms_fill_report_part_master_context()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare p public.parts%rowtype;
begin
  select * into p from public.parts where id=new.part_id and tenant_id=new.tenant_id;
  if p.id is null then raise exception 'A valid Part Master record is required'; end if;
  new.customer_id := p.customer_id;
  new.material_grade_id := p.material_grade_id;
  return new;
end;
$$;

revoke all on function public.qcms_fill_report_part_master_context() from public,anon;
grant execute on function public.qcms_fill_report_part_master_context() to authenticated;

drop trigger if exists trg_inspection_report_master_context on public.inspection_reports;
create trigger trg_inspection_report_master_context
before insert or update of part_id,customer_id,material_grade_id
on public.inspection_reports
for each row execute function public.qcms_fill_report_part_master_context();

drop trigger if exists trg_lab_test_master_context on public.lab_tests;
create trigger trg_lab_test_master_context
before insert or update of part_id,customer_id,material_grade_id
on public.lab_tests
for each row execute function public.qcms_fill_report_part_master_context();

commit;
