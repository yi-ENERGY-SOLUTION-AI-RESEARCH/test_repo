-- Bid Alert App — initial schema with RLS

create extension if not exists "pgcrypto";

-- alert_rules: user keyword / source settings
create table if not exists public.alert_rules (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null default '기본 규칙',
    keywords text[] not null default '{}',
    match_mode text not null default 'or' check (match_mode in ('and', 'or')),
    sources text[] not null default array['kepco'],
    notify_time time not null default '08:00:00',
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- notification_channels: email, slack, kakao per user
create table if not exists public.notification_channels (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    channel text not null check (channel in ('email', 'slack', 'kakao')),
    config jsonb not null default '{}',
    is_enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, channel)
);

-- sent_notices: deduplication log
create table if not exists public.sent_notices (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    rule_id uuid references public.alert_rules(id) on delete set null,
    source text not null,
    notice_id text not null,
    notice_title text not null,
    sent_at timestamptz not null default now(),
    channels text[] not null default '{}',
    unique (user_id, source, notice_id)
);

-- oauth_tokens: Kakao (and future providers)
create table if not exists public.oauth_tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    provider text not null default 'kakao',
    access_token text not null,
    refresh_token text,
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, provider)
);

create index if not exists idx_alert_rules_user_active
    on public.alert_rules (user_id) where is_active = true;

create index if not exists idx_sent_notices_user_source
    on public.sent_notices (user_id, source, notice_id);

-- updated_at trigger
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger alert_rules_updated_at
    before update on public.alert_rules
    for each row execute function public.set_updated_at();

create trigger notification_channels_updated_at
    before update on public.notification_channels
    for each row execute function public.set_updated_at();

create trigger oauth_tokens_updated_at
    before update on public.oauth_tokens
    for each row execute function public.set_updated_at();

-- RLS
alter table public.alert_rules enable row level security;
alter table public.notification_channels enable row level security;
alter table public.sent_notices enable row level security;
alter table public.oauth_tokens enable row level security;

-- alert_rules policies
create policy "Users select own alert_rules"
    on public.alert_rules for select
    using (auth.uid() = user_id);

create policy "Users insert own alert_rules"
    on public.alert_rules for insert
    with check (auth.uid() = user_id);

create policy "Users update own alert_rules"
    on public.alert_rules for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users delete own alert_rules"
    on public.alert_rules for delete
    using (auth.uid() = user_id);

-- notification_channels policies
create policy "Users select own channels"
    on public.notification_channels for select
    using (auth.uid() = user_id);

create policy "Users insert own channels"
    on public.notification_channels for insert
    with check (auth.uid() = user_id);

create policy "Users update own channels"
    on public.notification_channels for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users delete own channels"
    on public.notification_channels for delete
    using (auth.uid() = user_id);

-- sent_notices policies
create policy "Users select own sent_notices"
    on public.sent_notices for select
    using (auth.uid() = user_id);

create policy "Users insert own sent_notices"
    on public.sent_notices for insert
    with check (auth.uid() = user_id);

-- oauth_tokens policies
create policy "Users select own oauth_tokens"
    on public.oauth_tokens for select
    using (auth.uid() = user_id);

create policy "Users insert own oauth_tokens"
    on public.oauth_tokens for insert
    with check (auth.uid() = user_id);

create policy "Users update own oauth_tokens"
    on public.oauth_tokens for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users delete own oauth_tokens"
    on public.oauth_tokens for delete
    using (auth.uid() = user_id);

-- Service role bypasses RLS automatically.
