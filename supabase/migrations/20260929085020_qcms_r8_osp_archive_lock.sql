-- Permit row locking for the archive-only RPC without permitting header edits.
begin;
create policy archive_document_lock on public.osp_material_outs
for update to authenticated
using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('OSP_TRANSACTIONS','archive'))
with check (false);
commit;
