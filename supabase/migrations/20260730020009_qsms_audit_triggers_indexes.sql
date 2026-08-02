-- QSMS audit triggers, indexes, RLS and storage
begin;

-- -----------------------------------------------------------------------------
-- Updated-at and audit triggers
-- -----------------------------------------------------------------------------
do $$
declare
  table_name text;
  tracked_tables text[] := array[
    'tenants','profiles','parties','material_grades','material_grade_elements','parts',
    'part_supplier_links','processes','inspection_stages','quality_assets','inspection_plans',
    'inspection_plan_characteristics','test_plans','rmtc_approvals','inward_lots',
    'production_batches','batch_movements','osp_jobs','inspection_reports','inspection_results',
    'lab_tests','calculation_rules','ppap_projects','ppap_documents','pfd_headers','pfd_steps',
    'pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans',
    'spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies',
    'balloon_characteristics','calibration_events','audit_plans','audit_findings','dispatches',
    'dispatch_batches','customer_report_packages','customer_report_package_items','standards_register',
    'document_attachments','document_approvals','number_sequences'
  ];
begin
  foreach table_name in array tracked_tables loop
    execute format('drop trigger if exists trg_touch_updated_at on public.%I', table_name);
    execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', table_name);
    if table_name not in ('profiles','tenants') then
      execute format('drop trigger if exists trg_audit_row_change on public.%I', table_name);
      execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()', table_name);
    end if;
  end loop;
end;
$$;

-- -----------------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------------
create index if not exists idx_parts_tenant_customer on public.parts(tenant_id, customer_id);
create index if not exists idx_rmtc_heat on public.rmtc_approvals(tenant_id, heat_number, heat_code);
create index if not exists idx_inward_heat on public.inward_lots(tenant_id, heat_number, heat_code);
create index if not exists idx_batches_heat on public.production_batches(tenant_id, heat_number, heat_code);
create index if not exists idx_batches_parent on public.production_batches(parent_batch_id);
create index if not exists idx_batch_movements_batch on public.batch_movements(batch_id, movement_date);
create index if not exists idx_osp_source_child on public.osp_jobs(source_batch_id, osp_batch_id);
create index if not exists idx_inspection_source on public.inspection_reports(part_id, batch_id, inward_lot_id, osp_job_id);
create index if not exists idx_lab_source on public.lab_tests(part_id, batch_id, inward_lot_id, osp_job_id);
create index if not exists idx_ppap_part on public.ppap_projects(tenant_id, part_id, customer_id);
create index if not exists idx_calibration_due on public.quality_assets(tenant_id, next_due_date);
create index if not exists idx_audit_due on public.audit_plans(tenant_id, planned_date, status);
create index if not exists idx_audit_findings_due on public.audit_findings(tenant_id, target_date, status);
create index if not exists idx_dispatch_batch on public.dispatch_batches(batch_id);
create index if not exists idx_audit_log_row on public.audit_log(tenant_id, table_name, row_id, changed_at desc);

-- -----------------------------------------------------------------------------
-- Row Level Security
-- -----------------------------------------------------------------------------
alter table public.tenants enable row level security;
alter table public.profiles enable row level security;
alter table public.audit_log enable row level security;

drop policy if exists tenant_self_select on public.tenants;
create policy tenant_self_select on public.tenants
for select to authenticated
using (id = public.current_tenant_id());

drop policy if exists profile_tenant_select on public.profiles;
create policy profile_tenant_select on public.profiles
for select to authenticated
using (tenant_id = public.current_tenant_id());

drop policy if exists profile_self_update on public.profiles;
create policy profile_self_update on public.profiles
for update to authenticated
using (id = auth.uid())
with check (id = auth.uid() and tenant_id = public.current_tenant_id());

drop policy if exists profile_admin_update on public.profiles;
create policy profile_admin_update on public.profiles
for update to authenticated
using (tenant_id = public.current_tenant_id() and public.current_app_role() = 'ADMIN')
with check (tenant_id = public.current_tenant_id());

drop policy if exists audit_log_select on public.audit_log;
create policy audit_log_select on public.audit_log
for select to authenticated
using (tenant_id = public.current_tenant_id() and public.current_app_role() in ('ADMIN','QUALITY_MANAGER'));

do $$
declare
  table_name text;
  tenant_tables text[] := array[
    'parties','material_grades','material_grade_elements','parts','part_supplier_links','processes',
    'inspection_stages','quality_assets','inspection_plans','inspection_plan_characteristics','test_plans',
    'rmtc_approvals','inward_lots','production_batches','batch_movements','osp_jobs','inspection_reports',
    'inspection_results','lab_tests','calculation_rules','ppap_projects','ppap_documents','pfd_headers',
    'pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans',
    'spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies',
    'balloon_characteristics','calibration_events','audit_plans','audit_findings','dispatches',
    'dispatch_batches','customer_report_packages','customer_report_package_items','standards_register',
    'document_attachments','document_approvals','number_sequences'
  ];
begin
  foreach table_name in array tenant_tables loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('drop policy if exists tenant_select on public.%I', table_name);
    execute format('drop policy if exists tenant_insert on public.%I', table_name);
    execute format('drop policy if exists tenant_update on public.%I', table_name);
    execute format('drop policy if exists tenant_delete on public.%I', table_name);
    execute format(
      'create policy tenant_select on public.%I for select to authenticated using (tenant_id = public.current_tenant_id())',
      table_name
    );
    execute format(
      'create policy tenant_insert on public.%I for insert to authenticated with check (tenant_id = public.current_tenant_id() and public.can_write_table(%L))',
      table_name, table_name
    );
    execute format(
      'create policy tenant_update on public.%I for update to authenticated using (tenant_id = public.current_tenant_id() and public.can_write_table(%L)) with check (tenant_id = public.current_tenant_id() and public.can_write_table(%L))',
      table_name, table_name, table_name
    );
    execute format(
      'create policy tenant_delete on public.%I for delete to authenticated using (tenant_id = public.current_tenant_id() and public.current_app_role() = ''ADMIN'')',
      table_name
    );
  end loop;
end;
$$;

-- -----------------------------------------------------------------------------
-- Private Supabase Storage bucket and tenant-folder policies
-- Default app bucket is quality-documents. Change both migration and app settings together.
-- -----------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit)
values ('quality-documents', 'quality-documents', false, 52428800)
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit;

drop policy if exists qsms_storage_select on storage.objects;
create policy qsms_storage_select on storage.objects
for select to authenticated
using (
  bucket_id = 'quality-documents'
  and (storage.foldername(name))[1] = public.current_tenant_id()::text
);

drop policy if exists qsms_storage_insert on storage.objects;
create policy qsms_storage_insert on storage.objects
for insert to authenticated
with check (
  bucket_id = 'quality-documents'
  and (storage.foldername(name))[1] = public.current_tenant_id()::text
  and coalesce(public.current_app_role(), 'VIEWER') <> 'VIEWER'
);

drop policy if exists qsms_storage_update on storage.objects;
create policy qsms_storage_update on storage.objects
for update to authenticated
using (
  bucket_id = 'quality-documents'
  and (storage.foldername(name))[1] = public.current_tenant_id()::text
  and coalesce(public.current_app_role(), 'VIEWER') <> 'VIEWER'
)
with check (
  bucket_id = 'quality-documents'
  and (storage.foldername(name))[1] = public.current_tenant_id()::text
);

drop policy if exists qsms_storage_delete on storage.objects;
create policy qsms_storage_delete on storage.objects
for delete to authenticated
using (
  bucket_id = 'quality-documents'
  and (storage.foldername(name))[1] = public.current_tenant_id()::text
  and public.current_app_role() = 'ADMIN'
);

commit;
