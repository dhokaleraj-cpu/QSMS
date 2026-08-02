-- One-time, code-protected activation of the first QSMS administrator.
-- Only the SHA-256 hash is stored; the plaintext setup code is never committed.
begin;

create table if not exists public.qsms_bootstrap_control (
  id smallint primary key default 1 check (id = 1),
  code_hash text not null check (length(code_hash) = 64),
  used_at timestamptz,
  used_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
alter table public.qsms_bootstrap_control enable row level security;
revoke all on table public.qsms_bootstrap_control from public, anon, authenticated;

insert into public.qsms_bootstrap_control (id, code_hash)
values (1, '72be2bb0a05135726dcf3e7c8fa2487e5d755f727f353077f03fccc533cce214')
on conflict (id) do update
set code_hash = case
  when public.qsms_bootstrap_control.used_at is null then excluded.code_hash
  else public.qsms_bootstrap_control.code_hash
end;

create or replace function public.qsms_bootstrap_available()
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1 from public.qsms_bootstrap_control where id = 1 and used_at is null
  ) and not exists (
    select 1 from public.profiles where role = 'ADMIN' and status = 'ACTIVE'
  );
$$;
revoke all on function public.qsms_bootstrap_available() from public;
grant execute on function public.qsms_bootstrap_available() to anon, authenticated;

create or replace function public.protect_profile_privileges()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  actor_id uuid := auth.uid();
  actor_role text;
begin
  if actor_id is null then
    return new;
  end if;
  if current_setting('qsms.bootstrap_authorized', true) = 'true'
     and actor_id = old.id and old.role = 'VIEWER' and new.role = 'ADMIN' then
    new.tenant_id := old.tenant_id;
    new.status := 'ACTIVE';
    return new;
  end if;
  actor_role := public.current_app_role();
  if actor_role = 'ADMIN' then
    new.tenant_id := old.tenant_id;
    return new;
  end if;
  if actor_id <> old.id then
    raise exception 'Only an administrator can update another user profile';
  end if;
  new.tenant_id := old.tenant_id;
  new.role := old.role;
  new.status := old.status;
  return new;
end;
$$;
revoke all on function public.protect_profile_privileges() from public, anon, authenticated;

create or replace function public.qsms_claim_first_admin(
  p_setup_code text,
  p_full_name text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  actor_id uuid := auth.uid();
  expected_hash text;
  control_used timestamptz;
  claimed public.profiles%rowtype;
begin
  if actor_id is null then
    raise exception 'Sign in before claiming the first administrator account';
  end if;
  select code_hash, used_at
    into expected_hash, control_used
  from public.qsms_bootstrap_control
  where id = 1
  for update;
  if expected_hash is null then
    raise exception 'Administrator bootstrap is not configured';
  end if;
  if control_used is not null or exists (
    select 1 from public.profiles where role = 'ADMIN' and status = 'ACTIVE'
  ) then
    raise exception 'The first administrator has already been created';
  end if;
  if encode(digest(btrim(coalesce(p_setup_code, '')), 'sha256'), 'hex') <> expected_hash then
    raise exception 'Invalid one-time administrator setup code';
  end if;
  perform set_config('qsms.bootstrap_authorized', 'true', true);
  update public.profiles
  set full_name = coalesce(nullif(btrim(coalesce(p_full_name, '')), ''), full_name),
      role = 'ADMIN', status = 'ACTIVE', updated_at = now(), updated_by = actor_id
  where id = actor_id
  returning * into claimed;
  perform set_config('qsms.bootstrap_authorized', 'false', true);
  if claimed.id is null then
    raise exception 'The signed-in account has no QSMS profile';
  end if;
  update public.qsms_bootstrap_control set used_at = now(), used_by = actor_id where id = 1;
  return jsonb_build_object(
    'id', claimed.id, 'email', claimed.email, 'full_name', claimed.full_name,
    'role', claimed.role, 'status', claimed.status, 'tenant_id', claimed.tenant_id
  );
end;
$$;
revoke all on function public.qsms_claim_first_admin(text, text) from public, anon;
grant execute on function public.qsms_claim_first_admin(text, text) to authenticated;

commit;
