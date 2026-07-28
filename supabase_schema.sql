-- 사용자별 저장소 목록 (기존 localStorage 대체)
create table if not exists saved_repos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  repo text not null,
  created_at timestamptz default now(),
  unique(user_id, repo)
);

alter table saved_repos enable row level security;

create policy "select own repos" on saved_repos
  for select using (auth.uid() = user_id);
create policy "insert own repos" on saved_repos
  for insert with check (auth.uid() = user_id);
create policy "delete own repos" on saved_repos
  for delete using (auth.uid() = user_id);

-- 생성된 주간보고 이력
create table if not exists reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  markdown text not null,
  since date,
  until date,
  created_at timestamptz default now()
);

alter table reports enable row level security;

create policy "select own reports" on reports
  for select using (auth.uid() = user_id);
create policy "insert own reports" on reports
  for insert with check (auth.uid() = user_id);
create policy "delete own reports" on reports
  for delete using (auth.uid() = user_id);

-- 사용자별 설정 (표시 이름, 기본 조회 기간 등 기억)
create table if not exists user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  default_range_days integer,
  updated_at timestamptz default now()
);

alter table user_settings enable row level security;

create policy "select own settings" on user_settings
  for select using (auth.uid() = user_id);
create policy "insert own settings" on user_settings
  for insert with check (auth.uid() = user_id);
create policy "update own settings" on user_settings
  for update using (auth.uid() = user_id);
