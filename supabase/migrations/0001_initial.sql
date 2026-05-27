-- Flight monitor schema
create extension if not exists "pgcrypto";

create table public.searches (
    id              uuid        primary key default gen_random_uuid(),
    name            text        not null,
    active          boolean     not null default true,
    origin_iata     text        not null check (char_length(origin_iata) = 3),
    trip_type       text        not null default 'round_trip'
                                check (trip_type in ('round_trip','one_way')),
    outbound_window daterange   not null,
    duration_days   int4range,
    destinations    jsonb       not null,
    price_range     jsonb,
    filters         jsonb       not null default '{}'::jsonb,
    notify_on       jsonb       not null default '{}'::jsonb,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index searches_active_idx on public.searches (active) where active;

create table public.flight_results (
    id               uuid        primary key default gen_random_uuid(),
    search_id        uuid        not null references public.searches(id) on delete cascade,
    captured_at      timestamptz not null default now(),
    origin_iata      text        not null,
    destination_iata text        not null,
    departure_date   date        not null,
    return_date      date,
    price_eur        numeric(10,2) not null,
    airline          text,
    stops            int,
    duration_minutes int,
    deep_link        text,
    raw_offer        jsonb
);

create index flight_results_search_recent_idx
    on public.flight_results (search_id, captured_at desc);
create index flight_results_search_price_idx
    on public.flight_results (search_id, price_eur asc);

create table public.notifications_sent (
    id         uuid        primary key default gen_random_uuid(),
    search_id  uuid        not null references public.searches(id) on delete cascade,
    dedup_key  text        not null unique,
    sent_at    timestamptz not null default now()
);

create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

create trigger searches_touch_updated_at
    before update on public.searches
    for each row execute function public.touch_updated_at();

-- RLS: lock down by default; the service role bypasses RLS so backend and
-- Next.js server actions using the service key can read/write freely. Add
-- per-user policies later if exposing to multiple authenticated users.
alter table public.searches           enable row level security;
alter table public.flight_results     enable row level security;
alter table public.notifications_sent enable row level security;
