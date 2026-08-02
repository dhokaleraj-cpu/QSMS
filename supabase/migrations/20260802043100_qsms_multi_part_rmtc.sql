-- Multi-part RMTC worksheets and part-specific chemistry/Jominy/DI results.
begin;

alter table public.rmtc_chemistry_results
  add column if not exists part_id uuid references public.parts(id);
alter table public.rmtc_jominy_results
  add column if not exists part_id uuid references public.parts(id);

alter table public.rmtc_part_approvals
  add column if not exists grain_size integer,
  add column if not exists actual_di numeric,
  add column if not exists calculated_di numeric,
  add column if not exists actual_di_status text default 'NOT_EVALUATED',
  add column if not exists calculated_di_status text default 'NOT_EVALUATED';

alter table public.rmtc_part_approvals drop constraint if exists rmtc_part_approvals_actual_di_status_check;
alter table public.rmtc_part_approvals add constraint rmtc_part_approvals_actual_di_status_check
  check (actual_di_status in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_part_approvals drop constraint if exists rmtc_part_approvals_calculated_di_status_check;
alter table public.rmtc_part_approvals add constraint rmtc_part_approvals_calculated_di_status_check
  check (calculated_di_status in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_part_approvals drop constraint if exists rmtc_part_approvals_grain_size_check;
alter table public.rmtc_part_approvals add constraint rmtc_part_approvals_grain_size_check
  check (grain_size is null or grain_size between 4 and 8);

-- Backfill legacy records from the RMTC primary part.
update public.rmtc_chemistry_results c
   set part_id=r.part_id
  from public.rmtc_approvals r
 where c.rmtc_approval_id=r.id and c.part_id is null;
update public.rmtc_jominy_results j
   set part_id=r.part_id
  from public.rmtc_approvals r
 where j.rmtc_approval_id=r.id and j.part_id is null;

alter table public.rmtc_chemistry_results drop constraint if exists rmtc_chemistry_results_tenant_id_rmtc_approval_id_material__key;
alter table public.rmtc_jominy_results drop constraint if exists rmtc_jominy_results_tenant_id_rmtc_approval_id_jominy_dista_key;
create unique index if not exists uq_rmtc_chemistry_part_element
  on public.rmtc_chemistry_results(tenant_id,rmtc_approval_id,part_id,material_grade_element_id);
create unique index if not exists uq_rmtc_jominy_part_distance
  on public.rmtc_jominy_results(tenant_id,rmtc_approval_id,part_id,jominy_distance_id);

create index if not exists idx_rmtc_chemistry_part on public.rmtc_chemistry_results(rmtc_approval_id,part_id);
create index if not exists idx_rmtc_jominy_part on public.rmtc_jominy_results(rmtc_approval_id,part_id);

commit;
