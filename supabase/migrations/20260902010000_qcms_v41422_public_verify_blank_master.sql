-- QCMS v4.14.22 - public verifier marker for code-only master/RMTC state hotfix
-- Additive only. No business rows are deleted or reset.

create or replace function public.qcms_release_schema_version()
returns text
language sql
immutable
set search_path = pg_catalog
as $$ select '4.14.22'::text $$;

revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to anon, authenticated, service_role;

create or replace function public.qcms_release_contract_v41422()
returns text
language plpgsql
stable
set search_path = public, pg_catalog
as $$
begin
  if public.qcms_release_schema_version() = '4.14.22'
     and to_regprocedure('public.qcms_update_osp_material_out(uuid,date,text,numeric,date,text)') is not null
     and to_regprocedure('public.qcms_clear_osp_sample(uuid)') is not null
     and to_regprocedure('public.qcms_update_osp_receipt(uuid,date,text,text,date,text,date,text,numeric,text)') is not null
     and to_regprocedure('public.qcms_delete_osp_transaction(uuid)') is not null
     and to_regprocedure('public.qcms_delete_osp_receipt(uuid)') is not null
     and to_regprocedure('public.qcms_delete_transaction_row(text,uuid)') is not null
  then
    return 'QCMS_V41422_FULL_READY';
  end if;
  return 'QCMS_V41422_INCOMPLETE';
end;
$$;

revoke all on function public.qcms_release_contract_v41422() from public;
grant execute on function public.qcms_release_contract_v41422() to anon, authenticated, service_role;

insert into public.qcms_release_schema_state(version, build, details)
values ('4.14.22', '41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET', jsonb_build_object(
  'publishable_key_public_verify', true,
  'master_new_record_blank_state', true,
  'same_heat_rmtc_widget_reset', true,
  'transaction_delete_routing_preserved', true
))
on conflict (version) do update
set build = excluded.build, applied_at = now(), details = excluded.details;
