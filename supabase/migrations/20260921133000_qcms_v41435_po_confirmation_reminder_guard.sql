-- QCMS v4.14.35
-- Stop supplier PO confirmation reminders immediately after the current confirmation
-- is submitted/recorded, while preserving approval/receipt controls and revision genealogy.

create or replace function public.qcms_po_reminder_allowed(
  p_tenant_id uuid,
  p_purchase_order_id uuid,
  p_confirmation_id uuid default null
) returns boolean
language sql stable security definer set search_path=pg_catalog,public as $$
  select exists(
    select 1
      from public.supply_purchase_orders p
      join public.supply_po_confirmations c
        on c.purchase_order_id=p.id and c.tenant_id=p.tenant_id
     where p.tenant_id=p_tenant_id
       and p.id=p_purchase_order_id
       and (p_confirmation_id is null or c.id=p_confirmation_id)
       and upper(coalesce(p.approval_status,''))='APPROVED'
       and upper(coalesce(p.status,'')) not in ('CANCELLED','CLOSED')
       and upper(coalesce(c.confirmation_status,''))='PENDING'
       and coalesce(c.requested_at,c.created_at) is not null
       and not exists(
         select 1 from public.document_attachments a
          where a.tenant_id=c.tenant_id
            and a.entity_type='PO_CONFIRMATION'
            and a.entity_id=c.id
            and a.document_type='SUPPLIER_PO_CONFIRMATION'
            and a.status='ACTIVE'
            and a.created_at>=coalesce(c.requested_at,c.created_at)
       )
  );
$$;
revoke all on function public.qcms_po_reminder_allowed(uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.qcms_po_reminder_allowed(uuid,uuid,uuid) to service_role;

create or replace function public.qcms_is_po_confirmation_reminder(p_event text,p_template text)
returns boolean language sql immutable set search_path=pg_catalog as $$
  select coalesce(p_event,'')='PO_CONFIRMATION_REQUIRED'
      or coalesce(p_template,'') in ('PO_CONFIRMATION_REQUIRED','PO_CONFIRMATION_DAILY_DIGEST');
$$;

create or replace function public.qcms_outbox_po_reminder_allowed(p_row public.qcms_notification_outbox)
returns boolean language plpgsql stable security definer set search_path=pg_catalog,public as $$
declare poid uuid; confid uuid;
begin
  if not public.qcms_is_po_confirmation_reminder(p_row.event_key,p_row.template_key) then return true; end if;
  begin
    poid:=nullif(p_row.context->>'purchase_order_id','')::uuid;
    confid:=nullif(p_row.context->>'confirmation_id','')::uuid;
  exception when invalid_text_representation then return false;
  end;
  if p_row.related_table='supply_purchase_orders' then
    if poid is not null and poid is distinct from p_row.related_id then return false; end if;
    poid:=p_row.related_id;
  elsif p_row.related_table='supply_po_confirmations' then
    if confid is not null and confid is distinct from p_row.related_id then return false; end if;
    confid:=p_row.related_id;
  end if;
  if poid is null and confid is not null then
    select purchase_order_id into poid from public.supply_po_confirmations
     where id=confid and tenant_id=p_row.tenant_id;
  end if;
  if poid is null then return false; end if;
  return public.qcms_po_reminder_allowed(p_row.tenant_id,poid,confid);
end;
$$;
revoke all on function public.qcms_outbox_po_reminder_allowed(public.qcms_notification_outbox) from public,anon,authenticated;
grant execute on function public.qcms_outbox_po_reminder_allowed(public.qcms_notification_outbox) to service_role;

create or replace function public.qcms_guard_po_reminder_outbox()
returns trigger language plpgsql security definer set search_path=pg_catalog,public as $$
begin
  if new.status in ('PENDING','FAILED','SENDING')
     and public.qcms_is_po_confirmation_reminder(new.event_key,new.template_key)
     and not public.qcms_outbox_po_reminder_allowed(new) then
    new.status:='CANCELLED';
    new.last_error:='Reminder suppressed: current confirmation submitted/recorded, PO inactive, or invalid PO link.';
    new.updated_at:=now();
  end if;
  return new;
end;
$$;
drop trigger if exists qcms_po_reminder_outbox_guard on public.qcms_notification_outbox;
create trigger qcms_po_reminder_outbox_guard
before insert or update on public.qcms_notification_outbox
for each row execute function public.qcms_guard_po_reminder_outbox();

create or replace function public.qcms_cancel_obsolete_po_reminders()
returns trigger language plpgsql security definer set search_path=pg_catalog,public as $$
declare tid uuid;
begin
  if tg_table_name='document_attachments' then
    if new.entity_type<>'PO_CONFIRMATION' or new.document_type<>'SUPPLIER_PO_CONFIRMATION' then return new; end if;
  end if;
  tid:=new.tenant_id;
  update public.qcms_notification_outbox o
     set status='CANCELLED',updated_at=now(),
         last_error='Reminder suppressed: confirmation submitted/recorded or PO no longer awaiting response.'
   where o.tenant_id=tid
     and o.status in ('PENDING','FAILED','SENDING')
     and public.qcms_is_po_confirmation_reminder(o.event_key,o.template_key)
     and not public.qcms_outbox_po_reminder_allowed(o);
  return new;
end;
$$;
drop trigger if exists qcms_po_confirmation_cancel_reminders on public.supply_po_confirmations;
create trigger qcms_po_confirmation_cancel_reminders
after insert or update of confirmation_status,requested_at on public.supply_po_confirmations
for each row execute function public.qcms_cancel_obsolete_po_reminders();
drop trigger if exists qcms_po_attachment_cancel_reminders on public.document_attachments;
create trigger qcms_po_attachment_cancel_reminders
after insert or update of status,entity_id,document_type on public.document_attachments
for each row execute function public.qcms_cancel_obsolete_po_reminders();
drop trigger if exists qcms_po_status_cancel_reminders on public.supply_purchase_orders;
create trigger qcms_po_status_cancel_reminders
after update of status,approval_status on public.supply_purchase_orders
for each row execute function public.qcms_cancel_obsolete_po_reminders();

create or replace function public.qcms_claim_notification_for_send(p_outbox_id uuid,p_tenant_id uuid)
returns jsonb language plpgsql security definer set search_path=pg_catalog,public as $$
declare r public.qcms_notification_outbox%rowtype;
begin
  select * into r from public.qcms_notification_outbox
   where id=p_outbox_id and tenant_id=p_tenant_id for update;
  if not found or r.status not in ('PENDING','FAILED') then return null; end if;
  update public.qcms_notification_outbox
     set status='SENDING',attempts=coalesce(attempts,0)+1,last_error=null,updated_at=now()
   where id=r.id and tenant_id=p_tenant_id returning * into r;
  return to_jsonb(r);
end;
$$;
revoke all on function public.qcms_claim_notification_for_send(uuid,uuid) from public,anon,authenticated;
grant execute on function public.qcms_claim_notification_for_send(uuid,uuid) to service_role;

create or replace function public.qcms_notification_send_is_current(p_outbox_id uuid,p_tenant_id uuid)
returns boolean language sql stable security definer set search_path=pg_catalog,public as $$
  select exists(
    select 1 from public.qcms_notification_outbox o
     where o.id=p_outbox_id and o.tenant_id=p_tenant_id and o.status='SENDING'
       and public.qcms_outbox_po_reminder_allowed(o)
  );
$$;
revoke all on function public.qcms_notification_send_is_current(uuid,uuid) from public,anon,authenticated;
grant execute on function public.qcms_notification_send_is_current(uuid,uuid) to service_role;

update public.qcms_notification_outbox o
   set status='CANCELLED',updated_at=now(),
       last_error='v4.14.35: obsolete reminder cancelled after submission/confirmation or inactive PO.'
 where o.status in ('PENDING','FAILED')
   and public.qcms_is_po_confirmation_reminder(o.event_key,o.template_key)
   and not public.qcms_outbox_po_reminder_allowed(o);
