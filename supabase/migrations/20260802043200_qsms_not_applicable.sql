-- Allow explicit NOT_APPLICABLE disposition in RMTC detail grids.
begin;

alter table public.rmtc_chemistry_results drop constraint if exists rmtc_chemistry_results_result_check;
alter table public.rmtc_chemistry_results add constraint rmtc_chemistry_results_result_check
  check (result in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_jominy_results drop constraint if exists rmtc_jominy_results_result_check;
alter table public.rmtc_jominy_results add constraint rmtc_jominy_results_result_check
  check (result in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_requirement_results drop constraint if exists rmtc_requirement_results_result_check;
alter table public.rmtc_requirement_results add constraint rmtc_requirement_results_result_check
  check (result in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));

commit;
