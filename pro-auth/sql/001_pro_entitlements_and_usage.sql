-- DATA DADDY Pro: secure, per-account free-use accounting (development only).
-- Apply manually in Supabase SQL Editor after review. No Stripe billing is enabled.
create table if not exists public.pro_entitlements (
  user_id uuid primary key references auth.users(id) on delete cascade,
  plan text not null default 'free' check (plan in ('free','pro')),
  subscription_status text not null default 'inactive'
    check (subscription_status in ('inactive','active','trialing','past_due','canceled')),
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pro_tool_usage (
  user_id uuid not null references auth.users(id) on delete cascade,
  tool text not null check (tool in ('lineup_optimizer','player_comparison')),
  used_count integer not null default 0 check (used_count >= 0),
  updated_at timestamptz not null default now(),
  primary key (user_id, tool)
);

alter table public.pro_entitlements enable row level security;
alter table public.pro_tool_usage enable row level security;

-- Authenticated users may read their own status, but cannot grant themselves Pro.
revoke all on public.pro_entitlements from anon, authenticated;
revoke all on public.pro_tool_usage from anon, authenticated;
grant select on public.pro_entitlements to authenticated;
grant select on public.pro_tool_usage to authenticated;

drop policy if exists "Read own Pro entitlement" on public.pro_entitlements;
create policy "Read own Pro entitlement" on public.pro_entitlements
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Read own Pro usage" on public.pro_tool_usage;
create policy "Read own Pro usage" on public.pro_tool_usage
  for select to authenticated using (user_id = (select auth.uid()));

-- Only the server-side RPC may consume a free use. It serializes concurrent calls.
-- IMPORTANT: this is an accounting primitive, not yet a secure paywall:
-- the existing browser-only tools can still be run without this RPC.
create or replace function public.pro_consume_tool_use(p_tool text)
returns table(allowed boolean, reason text, uses_remaining integer)
language plpgsql security definer
set search_path = ''
as $$
declare
  v_user uuid := (select auth.uid());
  v_count integer;
  v_pro boolean;
begin
  if v_user is null then
    return query select false, 'login_required'::text, 0;
    return;
  end if;
  if p_tool not in ('lineup_optimizer','player_comparison') or p_tool is null then
    raise exception 'Unsupported tool';
  end if;
  -- Serialize all usage requests for a given account, including first use.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_user::text, 0));
  select (e.plan = 'pro' and e.subscription_status in ('active','trialing')
    and (e.current_period_end is null or e.current_period_end > now()))
    into v_pro
  from public.pro_entitlements e where e.user_id = v_user;
  if coalesce(v_pro, false) then
    return query select true, 'pro'::text, null::integer;
    return;
  end if;
  insert into public.pro_tool_usage(user_id,tool,used_count)
    values(v_user,p_tool,0) on conflict (user_id,tool) do nothing;
  select u.used_count into v_count from public.pro_tool_usage u
    where u.user_id = v_user and u.tool = p_tool for update;
  if v_count >= 1 then
    return query select false, 'free_limit_reached'::text, 0;
    return;
  end if;
  update public.pro_tool_usage u set used_count = used_count + 1, updated_at = now()
    where u.user_id = v_user and u.tool = p_tool;
  return query select true, 'free_use'::text, 0;
end;
$$;

revoke all on function public.pro_consume_tool_use(text) from public, anon;
grant execute on function public.pro_consume_tool_use(text) to authenticated;

-- IMPORTANT: Never grant clients INSERT/UPDATE on entitlement or usage tables.
-- Future Stripe webhook must verify Stripe signature and update entitlements
-- from a trusted server environment, not the public browser.
