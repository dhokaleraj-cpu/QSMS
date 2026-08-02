begin;
drop policy if exists bootstrap_no_direct_access on public.qsms_bootstrap_control;
create policy bootstrap_no_direct_access on public.qsms_bootstrap_control
for all to public
using (false)
with check (false);
commit;
