-- Run in Supabase SQL Editor. No dataset imports or fake data.
begin;
create table if not exists public.house_price_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    predicted_price_vnd numeric not null check (predicted_price_vnd > 0 and predicted_price_vnd < 1e16),
    predicted_price_per_m2 numeric not null check (predicted_price_per_m2 > 0 and predicted_price_per_m2 < 1e16),
    province text not null check (length(province) between 1 and 100),
    area_name text check (length(area_name) <= 100),
    property_type text check (length(property_type) <= 100),
    model_version text not null check (length(model_version) between 1 and 50),
    input_data jsonb check (input_data is null or (jsonb_typeof(input_data) = 'object' and octet_length(input_data::text) <= 8192))
);
create index if not exists house_price_history_owner_date on public.house_price_history (user_id, created_at desc, id desc);
alter table public.house_price_history enable row level security;
revoke all on public.house_price_history from anon, authenticated;
grant select, insert, delete on public.house_price_history to authenticated;
drop policy if exists house_price_select_own on public.house_price_history;
create policy house_price_select_own on public.house_price_history for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists house_price_insert_own on public.house_price_history;
create policy house_price_insert_own on public.house_price_history for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists house_price_delete_own on public.house_price_history;
create policy house_price_delete_own on public.house_price_history for delete to authenticated using ((select auth.uid()) = user_id);

create table if not exists public.market_area_stats (
    province text not null,
    area_name text not null default '',
    property_type text not null default '', -- empty = aggregate across observed types, not a fabricated asset type
    sample_count integer not null check (sample_count >= 5),
    median_price_vnd numeric not null check (median_price_vnd > 0),
    median_price_per_m2 numeric not null check (median_price_per_m2 > 0),
    p25 numeric not null check (p25 > 0),
    p75 numeric not null check (p75 >= p25),
    latest_date timestamptz not null,
    coverage text not null check (coverage in ('HIGH','MEDIUM','LOW','INSUFFICIENT')),
    source text not null,
    approved_source boolean not null default false,
    updated_at timestamptz not null default now(),
    primary key (province, area_name, property_type)
);
alter table public.market_area_stats enable row level security;
-- Optional per-m² quantiles used by the public market response. Additive migration.
alter table public.market_area_stats add column if not exists p25_price_per_m2 numeric check (p25_price_per_m2 > 0);
alter table public.market_area_stats add column if not exists p75_price_per_m2 numeric check (p75_price_per_m2 >= p25_price_per_m2);
revoke all on public.market_area_stats from anon, authenticated;
grant select on public.market_area_stats to anon, authenticated;
drop policy if exists market_stats_approved_read on public.market_area_stats;
create policy market_stats_approved_read on public.market_area_stats for select to anon, authenticated using (approved_source = true);

create table if not exists public.market_sync_runs (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    source text not null,
    status text not null check (status in ('success','failed')),
    valid_rows integer not null default 0 check (valid_rows >= 0),
    invalid_rows integer not null default 0 check (invalid_rows >= 0),
    stats_rows integer not null default 0 check (stats_rows >= 0)
);
alter table public.market_sync_runs enable row level security;
revoke all on public.market_sync_runs from anon, authenticated;
-- Market writes are server-side only. service_role stays in CI/server secrets.
grant all on public.market_area_stats, public.market_sync_runs to service_role;

-- Atomic replacement avoids stale rows from an older sync and partial publication.
create or replace function public.replace_approved_market_stats(stats jsonb, run_source text, valid_count integer, invalid_count integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
    if jsonb_typeof(stats) <> 'array' or jsonb_array_length(stats) = 0 then raise exception 'No validated market statistics'; end if;
    delete from public.market_area_stats;
    insert into public.market_area_stats (province, area_name, property_type, sample_count, median_price_vnd, median_price_per_m2, p25, p75, p25_price_per_m2, p75_price_per_m2, latest_date, coverage, source, approved_source)
    select x.province, x.area_name, x.property_type, x.sample_count, x.median_price_vnd, x.median_price_per_m2, x.p25, x.p75, x.p25_price_per_m2, x.p75_price_per_m2, x.latest_date, x.coverage, run_source, true
    from jsonb_to_recordset(stats) as x(province text, area_name text, property_type text, sample_count integer, median_price_vnd numeric, median_price_per_m2 numeric, p25 numeric, p75 numeric, p25_price_per_m2 numeric, p75_price_per_m2 numeric, latest_date timestamptz, coverage text);
    insert into public.market_sync_runs (source,status,valid_rows,invalid_rows,stats_rows) values (run_source,'success',valid_count,invalid_count,jsonb_array_length(stats));
end;
$$;
revoke all on function public.replace_approved_market_stats(jsonb,text,integer,integer) from public, anon, authenticated;
grant execute on function public.replace_approved_market_stats(jsonb,text,integer,integer) to service_role;
commit;
