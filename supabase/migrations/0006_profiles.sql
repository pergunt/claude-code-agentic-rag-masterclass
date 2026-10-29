-- Module 2.5.1: per-user profile row holding the admin flag.
-- Users can read their own row. There is no insert/update/delete policy, so nobody can promote
-- themselves through the API; admins are promoted in the SQL editor:
--   update public.profiles set is_admin = true where email = '<email>';

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  is_admin boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select using (id = (select auth.uid()));

-- Create a profile row for every new auth user.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill existing users.
insert into public.profiles (id, email)
select id, email from auth.users
on conflict do nothing;

-- True when the calling user is an admin. Definer so RLS policies on other tables can use it.
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((select is_admin from public.profiles where id = (select auth.uid())), false);
$$;

revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- Validate (SQL editor):
-- 1. Every auth user has a profile (expect 0):
--      select count(*) from auth.users u left join public.profiles p on p.id = u.id where p.id is null;
-- 2. No write policies, only select (expect one row: profiles_select_own / SELECT):
--      select policyname, cmd from pg_policies where tablename = 'profiles';
-- 3. anon cannot execute is_admin (expect false), authenticated can (expect true):
--      select has_function_privilege('anon', 'public.is_admin()', 'execute'),
--             has_function_privilege('authenticated', 'public.is_admin()', 'execute');
-- 4. Impersonation (one transaction); returns only that user's row, and the update changes 0 rows:
--      begin;
--      set local role authenticated;
--      set local request.jwt.claims = '{"sub":"<user uuid>","role":"authenticated"}';
--      select * from public.profiles;
--      update public.profiles set is_admin = true;
--      rollback;
-- 5. Promote an admin:
--      update public.profiles set is_admin = true where email = '<your account>';
