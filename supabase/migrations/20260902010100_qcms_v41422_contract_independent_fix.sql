-- QCMS v4.14.22 - independent public release verifier
-- Additive verifier-only change. No business data is changed.

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
