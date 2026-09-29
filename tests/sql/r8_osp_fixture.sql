-- Isolated PostgreSQL fixture for the R8 wrapper, not a production migration.
create role authenticated; create role anon;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('test.uid',true),'')::uuid$$;
create function public.current_tenant_id() returns uuid language sql stable as $$select nullif(current_setting('test.tenant',true),'')::uuid$$;
create function public.qcms_effective_module_permission(text,text) returns boolean language sql stable as $$select case when current_setting('test.archive_only',true)='true' then $2='archive' else coalesce(nullif(current_setting('test.allowed',true),''),'true')='true' end$$;
create function public.can_write_table(text) returns boolean language sql stable as $$select public.qcms_effective_module_permission('','')$$;
create function public.touch_updated_at() returns trigger language plpgsql as $$begin new.updated_at=now(); return new; end$$;
create function public.log_row_change() returns trigger language plpgsql as $$begin return null; end$$;
create table public.tenants(id uuid primary key);
create table public.inward_lots(id uuid primary key,tenant_id uuid,part_id uuid,heat_number text,available numeric);
create table public.supply_opening_stock(like public.inward_lots including all);
create table public.part_process_specifications(id uuid primary key,tenant_id uuid,part_id uuid,process_id uuid,status text,inward_type text);
create table public.osp_jobs(id uuid primary key default gen_random_uuid(),tenant_id uuid,osp_job_number text,source_inward_lot_id uuid,opening_stock_id uuid,source_batch_id uuid,osp_batch_id uuid,part_id uuid,vendor_id uuid,process_id uuid,process_specification_id uuid,dispatch_date date,dispatch_challan text,quantity_dispatched numeric,expected_return_date date,sample_quantity numeric,dispatch_remarks text,sample_received_date date,quantity_received numeric default 0,status text default 'AT_VENDOR',sample_gate_status text default 'PENDING');
create function public.qsms_create_osp_dispatch(p_inward_lot_id uuid,p_vendor_id uuid,p_process_id uuid,p_process_specification_id uuid,p_dispatch_date date,p_dispatch_challan text,p_quantity_dispatched numeric,p_expected_return_date date,p_sample_quantity numeric,p_remarks text) returns jsonb language plpgsql as $$
declare src public.inward_lots%rowtype; j public.osp_jobs%rowtype;
begin
 select * into src from public.inward_lots where id=p_inward_lot_id for update;
 if src.available<p_quantity_dispatched then raise exception 'Quantity exceeds available source balance'; end if;
 update public.inward_lots set available=available-p_quantity_dispatched where id=src.id;
 insert into public.osp_jobs(tenant_id,osp_job_number,source_inward_lot_id,part_id,vendor_id,process_id,process_specification_id,dispatch_date,dispatch_challan,quantity_dispatched,expected_return_date,sample_quantity,dispatch_remarks,source_batch_id,osp_batch_id)
 values(src.tenant_id,'OSP-'||substr(gen_random_uuid()::text,1,8),src.id,src.part_id,p_vendor_id,p_process_id,p_process_specification_id,p_dispatch_date,p_dispatch_challan,p_quantity_dispatched,p_expected_return_date,p_sample_quantity,p_remarks,gen_random_uuid(),gen_random_uuid()) returning * into j;
 return to_jsonb(j);
end$$;
create function public.qsms_create_osp_dispatch_from_opening_stock(uuid,uuid,uuid,uuid,date,text,numeric,date,numeric,text) returns jsonb language plpgsql as $$begin raise exception 'Fixture opening stock is unavailable'; end$$;
create function public.qcms_update_osp_material_out(p_osp_job_id uuid,p_dispatch_date date,p_dispatch_challan text,p_quantity_dispatched numeric,p_expected_return_date date,p_remarks text) returns jsonb language plpgsql as $$
declare j public.osp_jobs%rowtype; delta numeric;
begin
 select * into j from public.osp_jobs where id=p_osp_job_id for update;
 if j.sample_received_date is not null or j.quantity_received>0 then raise exception 'Downstream sample/receipt exists'; end if;
 if p_quantity_dispatched<=0 or p_quantity_dispatched<j.sample_quantity then raise exception 'Invalid quantity'; end if;
 delta:=p_quantity_dispatched-j.quantity_dispatched;
 if delta>(select available from public.inward_lots where id=j.source_inward_lot_id) then raise exception 'Exceeds source balance'; end if;
 update public.inward_lots set available=available-delta where id=j.source_inward_lot_id;
 update public.osp_jobs set dispatch_date=p_dispatch_date,dispatch_challan=p_dispatch_challan,expected_return_date=p_expected_return_date,quantity_dispatched=p_quantity_dispatched,dispatch_remarks=p_remarks where id=j.id returning * into j;
 return to_jsonb(j);
end$$;
create function public.qcms_delete_osp_transaction(p_osp_job_id uuid) returns jsonb language plpgsql as $$
declare j public.osp_jobs%rowtype;
begin
 select * into j from public.osp_jobs where id=p_osp_job_id;
 if j.sample_received_date is not null or j.quantity_received>0 then raise exception 'Downstream sample/receipt exists'; end if;
 update public.inward_lots set available=available+j.quantity_dispatched where id=j.source_inward_lot_id;
 delete from public.osp_jobs where id=j.id;
 return jsonb_build_object('deleted',true);
end$$;
grant usage on schema auth to authenticated;
grant select,update,insert,delete on all tables in schema public to authenticated;
select set_config('test.uid','00000000-0000-0000-0000-000000000001',false);
select set_config('test.tenant','00000000-0000-0000-0000-000000000010',false);
insert into public.tenants values('00000000-0000-0000-0000-000000000010');
insert into public.part_process_specifications values('00000000-0000-0000-0000-000000000020','00000000-0000-0000-0000-000000000010','00000000-0000-0000-0000-000000000030','00000000-0000-0000-0000-000000000040','ACTIVE','OSP_PROCESS');
insert into public.inward_lots values
('00000000-0000-0000-0000-000000000051','00000000-0000-0000-0000-000000000010','00000000-0000-0000-0000-000000000030','HEAT-A',100),
('00000000-0000-0000-0000-000000000052','00000000-0000-0000-0000-000000000010','00000000-0000-0000-0000-000000000030','HEAT-B',200),
('00000000-0000-0000-0000-000000000053','00000000-0000-0000-0000-000000000099','00000000-0000-0000-0000-000000000030','FOREIGN',200),
('00000000-0000-0000-0000-000000000054','00000000-0000-0000-0000-000000000010','00000000-0000-0000-0000-000000000031','OTHER-PART',200);
