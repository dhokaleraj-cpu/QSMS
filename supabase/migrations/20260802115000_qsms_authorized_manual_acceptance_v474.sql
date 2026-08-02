-- QSMS 4.7.4: authorized approver may manually accept a failed automated RMTC recommendation.
-- Manual overrides require a reason and remain in the part approval audit snapshot.

begin;

alter table public.rmtc_approvals
  drop constraint if exists rmtc_approvals_check;

alter table public.rmtc_approvals
  add constraint rmtc_approvals_check
  check (
    status not in ('APPROVED','PARTIALLY_APPROVED')
    or disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
  );

create or replace function public.qsms_decide_rmtc(
  p_rmtc_id uuid,
  p_decisions jsonb,
  p_approved_by_employee_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
  v_role text := public.current_app_role();
  v_item jsonb;
  v_part_id uuid;
  v_disposition text;
  v_reason text;
  v_auto_status text;
  v_override boolean;
  v_total integer := 0;
  v_accepted integer := 0;
  v_reserve integer := 0;
  v_rejected integer := 0;
  v_pending integer := 0;
  v_hold integer := 0;
  v_header_disposition text;
  v_header_status text;
  v_is_final boolean := false;
begin
  if v_role not in ('ADMIN','QUALITY_MANAGER','METLAB_APPROVER') and not exists(
    select 1
    from public.user_module_permissions p
    where p.profile_id = auth.uid()
      and p.tenant_id = public.current_tenant_id()
      and p.module_key = 'RMTC_ENTRY'
      and p.can_approve = true
  ) then
    raise exception 'Your user does not have RMTC approval permission';
  end if;

  select * into v_header
  from public.rmtc_approvals
  where id = p_rmtc_id
    and tenant_id = public.current_tenant_id()
  for update;

  if v_header.id is null then raise exception 'RMTC record was not found'; end if;
  if v_header.status <> 'APPROVAL_PENDING' then
    raise exception 'RMTC must be Approval Pending before decision';
  end if;
  if v_header.validated_at is null then
    raise exception 'RMTC validation must be completed before decision';
  end if;
  if not public.qsms_employee_has_authority(p_approved_by_employee_id,'RMTC_APPROVE') then
    raise exception 'The selected approver does not have RMTC approval authority';
  end if;
  if jsonb_typeof(p_decisions) <> 'array' or jsonb_array_length(p_decisions) = 0 then
    raise exception 'Select a decision for each covered Part Number';
  end if;

  perform public.qsms_evaluate_rmtc(p_rmtc_id);

  for v_item in select value from jsonb_array_elements(p_decisions)
  loop
    v_part_id := nullif(v_item->>'part_id','')::uuid;
    v_disposition := upper(replace(btrim(coalesce(v_item->>'disposition','')),' ','_'));
    v_reason := nullif(btrim(coalesce(v_item->>'reason','')),'');

    if v_disposition not in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then
      raise exception 'Invalid RMTC decision for Part %', v_part_id;
    end if;

    select approval_status into v_auto_status
    from public.rmtc_part_approvals
    where rmtc_approval_id = p_rmtc_id
      and part_id = v_part_id
    for update;

    if v_auto_status is null then
      raise exception 'Part decision does not belong to the selected RMTC';
    end if;

    v_override := (v_disposition = 'ACCEPTED' and v_auto_status <> 'APPROVED');

    if v_override and v_reason is null then
      raise exception 'Manual acceptance reason is mandatory when accepting a failed automated recommendation';
    end if;
    if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and v_reason is null then
      raise exception 'A reason is mandatory for On Hold, Accepted Under Reserve or Rejected decisions';
    end if;

    update public.rmtc_part_approvals
    set disposition = v_disposition,
        decision_reason = v_reason,
        decision_at = case
          when v_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then now()
          else null
        end,
        decision_by_employee_id = p_approved_by_employee_id,
        approval_reason = coalesce(approval_reason,'{}'::jsonb) || case
          when v_override then jsonb_build_object(
            'manual_override', true,
            'automated_recommendation', v_auto_status,
            'override_reason', v_reason,
            'override_by', auth.uid(),
            'override_role', v_role,
            'override_at', now()
          )
          else '{}'::jsonb
        end,
        updated_at = now(),
        updated_by = auth.uid()
    where rmtc_approval_id = p_rmtc_id
      and part_id = v_part_id;

    v_total := v_total + 1;
    case v_disposition
      when 'ACCEPTED' then v_accepted := v_accepted + 1;
      when 'ACCEPTED_UNDER_RESERVE' then v_reserve := v_reserve + 1;
      when 'REJECTED' then v_rejected := v_rejected + 1;
      when 'ON_HOLD' then v_hold := v_hold + 1;
      else v_pending := v_pending + 1;
    end case;
  end loop;

  if v_total <> (
    select count(*) from public.rmtc_part_approvals where rmtc_approval_id = p_rmtc_id
  ) then
    raise exception 'A decision row is required for every covered Part Number';
  end if;

  if v_pending > 0 then
    v_header_disposition := 'PENDING';
    v_header_status := 'APPROVAL_PENDING';
  elsif v_hold > 0 then
    v_header_disposition := 'ON_HOLD';
    v_header_status := 'APPROVAL_PENDING';
  else
    v_is_final := true;
    v_header_disposition := case
      when v_accepted = 0 and v_reserve = 0 then 'REJECTED'
      when v_reserve > 0 then 'ACCEPTED_UNDER_RESERVE'
      else 'ACCEPTED'
    end;
    v_header_status := case
      when v_rejected = v_total then 'REJECTED'
      when v_rejected > 0 then 'PARTIALLY_APPROVED'
      else 'APPROVED'
    end;
  end if;

  update public.rmtc_approvals
  set disposition = v_header_disposition,
      disposition_reason = case
        when v_header_disposition = 'ON_HOLD' then 'One or more covered parts are On Hold'
        when v_header_disposition = 'ACCEPTED_UNDER_RESERVE' then 'One or more covered parts accepted under reserve'
        when v_header_disposition = 'REJECTED' then 'All covered parts rejected'
        else null
      end,
      decision_at = case when v_is_final then now() else null end,
      decision_by_employee_id = p_approved_by_employee_id,
      approved_by_employee_id = p_approved_by_employee_id,
      approved_at = case when v_is_final then now() else null end,
      approved_by = case when v_is_final then auth.uid() else null end,
      status = v_header_status,
      rejection_reason = case
        when v_header_status = 'REJECTED' then 'All covered Part Numbers were rejected'
        else null
      end,
      updated_at = now(),
      updated_by = auth.uid()
  where id = p_rmtc_id;

  return jsonb_build_object(
    'status', v_header_status,
    'disposition', v_header_disposition,
    'part_count', v_total,
    'pending', v_pending,
    'on_hold', v_hold,
    'accepted', v_accepted,
    'accepted_under_reserve', v_reserve,
    'rejected', v_rejected,
    'finalized', v_is_final
  );
end;
$$;

revoke all on function public.qsms_decide_rmtc(uuid,jsonb,uuid) from public, anon;
grant execute on function public.qsms_decide_rmtc(uuid,jsonb,uuid) to authenticated;

commit;
