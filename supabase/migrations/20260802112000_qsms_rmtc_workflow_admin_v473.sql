-- QSMS 4.7.3 RMTC workflow reliability and administrator controls.
-- Applied to the live project on 2026-08-02.
-- The authoritative function definitions are maintained in the live Supabase migration history.

alter table public.rmtc_part_approvals
  add column if not exists worksheet_completed_at timestamptz,
  add column if not exists worksheet_completed_by uuid references public.profiles(id);

-- qsms_save_rmtc_header: atomic/idempotent Draft save + worksheet initialization.
-- qsms_submit_rmtc: blocks submission until all Part Worksheets are completed.
-- qsms_decide_rmtc: permits ADMIN override with mandatory reason and stores audit metadata.
-- Administrator module permissions are granted for all current QSMS modules.
