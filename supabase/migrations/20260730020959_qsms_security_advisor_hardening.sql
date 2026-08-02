-- Revoke direct API execution from trigger-only functions and pin search_path.
begin;
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = public, auth
as $$
begin
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end;
$$;
revoke all on function public.touch_updated_at() from public, anon, authenticated;
revoke all on function public.handle_new_user() from public, anon, authenticated;
revoke all on function public.log_row_change() from public, anon, authenticated;
revoke all on function public.enforce_inward_rmtc_link() from public, anon, authenticated;
revoke all on function public.enforce_batch_genealogy() from public, anon, authenticated;
revoke all on function public.enforce_osp_genealogy() from public, anon, authenticated;
commit;
