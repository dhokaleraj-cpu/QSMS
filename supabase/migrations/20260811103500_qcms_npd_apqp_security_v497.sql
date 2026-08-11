-- QCMS 4.9.7 — NPD / APQP security hardening
begin;

alter function public.qsms_module_for_table(text) set search_path = public;

commit;
