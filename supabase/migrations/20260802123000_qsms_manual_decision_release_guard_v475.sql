-- QSMS 4.7.5
-- Final authorized RMTC dispositions control release eligibility.
-- Automated approval_status remains visible as a recommendation and does not block
-- a reasoned manual acceptance by an authorized approver.

begin;

create or replace function public.enforce_rmtc_master_link()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  part_row public.parts%rowtype;
  already_received numeric;
  v_parts integer := 0;
  v_release_decisions integer := 0;
  v_rejected_decisions integer := 0;
  v_final_decisions integer := 0;
  v_missing_override_reasons integer := 0;
begin
  select * into part_row from public.parts where id = new.part_id;
  if part_row.id is null or part_row.tenant_id <> new.tenant_id then
    raise exception 'Invalid part for RMTC approval';
  end if;
  if part_row.material_grade_id is null then
    raise exception 'The selected part has no controlled material grade';
  end if;
  new.material_grade_id := part_row.material_grade_id;

  select coalesce(sum(quantity_received),0)
    into already_received
    from public.inward_lots
   where rmtc_approval_id = new.id;
  if already_received > new.certificate_quantity then
    raise exception 'RMTC certificate quantity cannot be reduced below material already inwarded';
  end if;

  if new.status in ('APPROVED','PARTIALLY_APPROVED') then
    select
      count(*),
      count(*) filter(where disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')),
      count(*) filter(where disposition = 'REJECTED'),
      count(*) filter(where disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED')),
      count(*) filter(
        where (
          (disposition = 'ACCEPTED' and approval_status <> 'APPROVED')
          or disposition in ('ACCEPTED_UNDER_RESERVE','REJECTED')
        )
        and nullif(btrim(coalesce(decision_reason,'')),'') is null
      )
      into v_parts, v_release_decisions, v_rejected_decisions,
           v_final_decisions, v_missing_override_reasons
      from public.rmtc_part_approvals
     where rmtc_approval_id = new.id;

    if v_parts = 0 then
      raise exception 'RMTC release requires at least one covered Part Number';
    end if;
    if v_final_decisions <> v_parts then
      raise exception 'RMTC release requires a final decision for every covered Part Number';
    end if;
    if v_release_decisions = 0 then
      raise exception 'RMTC release requires at least one Accepted or Accepted Under Reserve Part Number';
    end if;
    if v_missing_override_reasons > 0 then
      raise exception 'A manual acceptance, reserve or rejection reason is mandatory';
    end if;
    if new.status = 'APPROVED' and (
      v_release_decisions <> v_parts or v_rejected_decisions <> 0
    ) then
      raise exception 'APPROVED RMTC status requires every covered Part Number to be Accepted or Accepted Under Reserve';
    end if;
    if new.status = 'PARTIALLY_APPROVED' and (
      v_release_decisions = 0 or v_rejected_decisions = 0
    ) then
      raise exception 'PARTIALLY APPROVED RMTC status requires both released and rejected Part Numbers';
    end if;
    if new.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
      raise exception 'RMTC release requires an Accepted or Accepted Under Reserve final disposition';
    end if;
    if new.certificate_quantity <= 0 then
      raise exception 'RMTC release requires a positive certificate quantity';
    end if;
    if new.approved_by_employee_id is null then
      raise exception 'RMTC release requires the selected approving employee';
    end if;

    new.approved_at := coalesce(new.approved_at, now());
    new.approved_by := coalesce(new.approved_by, auth.uid());
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_rmtc_master_link() from public, anon, authenticated;

commit;
