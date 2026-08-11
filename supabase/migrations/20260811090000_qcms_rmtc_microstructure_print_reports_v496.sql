-- QCMS 4.9.6 - RMTC microstructure photographs and controlled print enhancements.
begin;

alter table public.rmtc_approvals
  add column if not exists microstructure_image_1_path text,
  add column if not exists microstructure_image_2_path text,
  add column if not exists microstructure_image_3_path text,
  add column if not exists microstructure_caption_1 text,
  add column if not exists microstructure_caption_2 text,
  add column if not exists microstructure_caption_3 text;

comment on column public.rmtc_approvals.microstructure_image_1_path is 'Private storage path for RMTC microstructure photograph 1';
comment on column public.rmtc_approvals.microstructure_image_2_path is 'Private storage path for RMTC microstructure photograph 2';
comment on column public.rmtc_approvals.microstructure_image_3_path is 'Private storage path for RMTC microstructure photograph 3';
comment on column public.rmtc_approvals.microstructure_caption_1 is 'Caption for RMTC microstructure photograph 1';
comment on column public.rmtc_approvals.microstructure_caption_2 is 'Caption for RMTC microstructure photograph 2';
comment on column public.rmtc_approvals.microstructure_caption_3 is 'Caption for RMTC microstructure photograph 3';

commit;
