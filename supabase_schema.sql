-- Space Ops Room v0.3
-- Run this once in Supabase SQL Editor.

create table if not exists public.space_weather (
  observed_at timestamptz primary key,
  kp double precision not null,
  g_scale integer not null default 0,
  r_scale integer not null default 0,
  s_scale integer not null default 0,
  source text not null,
  collected_at timestamptz not null default now()
);

create table if not exists public.gnss_cells (
  mode text not null,
  observed_at timestamptz not null,
  granularity text not null,
  h3_index text not null,
  lat double precision not null,
  lon double precision not null,
  affected_pct double precision not null default 0,
  affected_count integer not null default 0,
  total_count integer not null default 0,
  collected_at timestamptz not null default now(),
  source text not null,
  primary key (mode, observed_at, h3_index)
);

create index if not exists gnss_cells_time_idx on public.gnss_cells(observed_at desc);
create index if not exists gnss_cells_lat_lon_idx on public.gnss_cells(lat, lon);

create table if not exists public.gnss_aoi_snapshots (
  observed_at timestamptz not null,
  aoi text not null,
  mode text not null,
  score double precision not null default 0,
  status text not null,
  confidence text not null,
  affected_cells integer not null default 0,
  max_pct double precision not null default 0,
  aircraft_count integer not null default 0,
  granularity text not null,
  source text not null,
  primary key (observed_at, aoi, mode)
);

create index if not exists gnss_aoi_time_idx on public.gnss_aoi_snapshots(observed_at desc);

create table if not exists public.gnss_events (
  event_key text primary key,
  mode text not null,
  observed_date date,
  start_time text,
  end_time text,
  lat double precision not null,
  lon double precision not null,
  collected_at timestamptz not null default now(),
  source text not null
);

create table if not exists public.orbital_elements (
  collected_at timestamptz not null,
  group_name text not null,
  norad_cat_id text not null,
  object_name text,
  object_id text,
  epoch text,
  mean_motion double precision,
  eccentricity double precision,
  inclination double precision,
  ra_of_asc_node double precision,
  arg_of_pericenter double precision,
  mean_anomaly double precision,
  bstar double precision,
  semi_major_axis_km double precision,
  source text not null,
  primary key (collected_at, group_name, norad_cat_id)
);

create index if not exists orbital_elements_lookup_idx
  on public.orbital_elements(group_name, norad_cat_id, collected_at desc);

create table if not exists public.orbital_events (
  event_key text primary key,
  detected_at timestamptz not null,
  norad_cat_id text not null,
  object_name text,
  group_name text,
  event_type text not null,
  severity text not null,
  confidence text not null,
  summary text not null,
  metrics jsonb,
  status text not null default 'OPEN',
  source text not null
);

create index if not exists orbital_events_time_idx on public.orbital_events(detected_at desc);

create table if not exists public.collector_status (
  source text primary key,
  last_success timestamptz not null,
  detail text,
  rows_written integer not null default 0
);

create or replace view public.latest_gnss_cells as
select g.*
from public.gnss_cells g
join (
  select mode, max(observed_at) as observed_at
  from public.gnss_cells
  group by mode
) m
on m.mode = g.mode and m.observed_at = g.observed_at;

create or replace view public.latest_orbital_elements as
select distinct on (group_name, norad_cat_id)
  *
from public.orbital_elements
order by group_name, norad_cat_id, collected_at desc;

-- Public read access through the anon/publishable key.
-- Writes remain restricted to the service-role key used by GitHub Actions.
alter table public.space_weather enable row level security;
alter table public.gnss_cells enable row level security;
alter table public.gnss_aoi_snapshots enable row level security;
alter table public.gnss_events enable row level security;
alter table public.orbital_elements enable row level security;
alter table public.orbital_events enable row level security;
alter table public.collector_status enable row level security;

drop policy if exists "public read space_weather" on public.space_weather;
create policy "public read space_weather" on public.space_weather for select using (true);

drop policy if exists "public read gnss_cells" on public.gnss_cells;
create policy "public read gnss_cells" on public.gnss_cells for select using (true);

drop policy if exists "public read gnss_aoi_snapshots" on public.gnss_aoi_snapshots;
create policy "public read gnss_aoi_snapshots" on public.gnss_aoi_snapshots for select using (true);

drop policy if exists "public read gnss_events" on public.gnss_events;
create policy "public read gnss_events" on public.gnss_events for select using (true);

drop policy if exists "public read orbital_elements" on public.orbital_elements;
create policy "public read orbital_elements" on public.orbital_elements for select using (true);

drop policy if exists "public read orbital_events" on public.orbital_events;
create policy "public read orbital_events" on public.orbital_events for select using (true);

drop policy if exists "public read collector_status" on public.collector_status;
create policy "public read collector_status" on public.collector_status for select using (true);

grant select on public.latest_gnss_cells to anon, authenticated;
grant select on public.latest_orbital_elements to anon, authenticated;
