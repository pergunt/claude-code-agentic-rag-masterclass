-- Module 2.5.2: global runtime settings (admin overrides of the env defaults) and Vault-backed API keys.
-- One row; every override is nullable (null = use the env default). Only admins can read/update it.
-- API keys live in Supabase Vault as secrets named 'app:llm_api_key' / 'app:embedding_api_key'.
-- Admins write them via set_app_secret; only the backend (service_role) can decrypt, via get_app_secrets.

create table if not exists public.app_settings (
  id boolean primary key default true check (id),
  llm_base_url text,
  llm_model text,
  embedding_base_url text,
  embedding_model text,
  updated_at timestamptz,
  updated_by uuid
);

insert into public.app_settings (id) values (true) on conflict do nothing;

alter table public.app_settings enable row level security;

drop policy if exists "app_settings_select_admin" on public.app_settings;
create policy "app_settings_select_admin" on public.app_settings
  for select using (public.is_admin());

drop policy if exists "app_settings_update_admin" on public.app_settings;
create policy "app_settings_update_admin" on public.app_settings
  for update using (public.is_admin()) with check (public.is_admin());
-- No insert/delete policies: the single row is managed by this migration only.

-- Which embedding model produced a document's chunks (null = unknown, pre-2.5).
alter table public.documents add column if not exists embedding_model text;
-- Everything ingested before 2.5 used the then-only model, so it isn't stale.
update public.documents set embedding_model = 'text-embedding-3-small'
where embedding_model is null and status = 'completed';

create extension if not exists supabase_vault;

-- Admin: set or clear a secret. Empty/null value deletes it.
create or replace function public.set_app_secret(p_name text, p_value text)
returns void
language plpgsql
security definer
set search_path = public, vault
as $$
declare
  v_id uuid;
  v_key text := 'app:' || p_name;
begin
  if not public.is_admin() then
    raise exception 'Admin only' using errcode = '42501';
  end if;
  if p_name is null or p_name not in ('llm_api_key', 'embedding_api_key') then
    raise exception 'Unknown secret name' using errcode = '22023';
  end if;

  select id into v_id from vault.secrets where name = v_key;

  if p_value is null or btrim(p_value) = '' then
    if v_id is not null then
      delete from vault.secrets where id = v_id;
    end if;
  elsif v_id is null then
    perform vault.create_secret(p_value, v_key, 'App setting ' || p_name);
  else
    perform vault.update_secret(v_id, p_value, v_key);
  end if;
end;
$$;

revoke execute on function public.set_app_secret(text, text) from public, anon;
grant execute on function public.set_app_secret(text, text) to authenticated;

-- Admin: which secrets are set, when, and the last 4 characters.
create or replace function public.app_secret_status()
returns table (name text, updated_at timestamptz, last4 text)
language plpgsql
stable
security definer
set search_path = public, vault
as $$
begin
  if not public.is_admin() then
    raise exception 'Admin only' using errcode = '42501';
  end if;
  return query
    select substr(s.name, 5) as name, s.updated_at, right(s.decrypted_secret, 4) as last4
    from vault.decrypted_secrets s
    where s.name in ('app:llm_api_key', 'app:embedding_api_key');
end;
$$;

revoke execute on function public.app_secret_status() from public, anon;
grant execute on function public.app_secret_status() to authenticated;

-- Backend only: decrypted keys. Never callable with a user JWT.
create or replace function public.get_app_secrets()
returns table (name text, decrypted_secret text)
language sql
stable
security definer
set search_path = public, vault
as $$
  select substr(s.name, 5) as name, s.decrypted_secret
  from vault.decrypted_secrets s
  where s.name in ('app:llm_api_key', 'app:embedding_api_key');
$$;

revoke all on function public.get_app_secrets() from public, anon, authenticated;
grant execute on function public.get_app_secrets() to service_role;

-- Validate (SQL editor):
-- 1. Vault is installed (expect one row):
--      select extname from pg_extension where extname = 'supabase_vault';
-- 2. get_app_secrets is service_role only (expect false, false, true):
--      select has_function_privilege('anon', 'public.get_app_secrets()', 'execute'),
--             has_function_privilege('authenticated', 'public.get_app_secrets()', 'execute'),
--             has_function_privilege('service_role', 'public.get_app_secrets()', 'execute');
-- 3. Exactly one settings row, RLS on, select + update policies only:
--      select count(*) from public.app_settings;
--      select policyname, cmd from pg_policies where tablename = 'app_settings';
-- 4. Non-admin impersonation (one transaction): select returns 0 rows, set_app_secret raises 'Admin only':
--      begin;
--      set local role authenticated;
--      set local request.jwt.claims = '{"sub":"<non-admin uuid>","role":"authenticated"}';
--      select * from public.app_settings;
--      select public.set_app_secret('llm_api_key', 'x');
--      rollback;
-- 5. Admin round trip (use an admin uuid; rollback leaves nothing behind):
--      begin;
--      set local role authenticated;
--      set local request.jwt.claims = '{"sub":"<admin uuid>","role":"authenticated"}';
--      select public.set_app_secret('embedding_api_key', 'dummy-key-1234567890');
--      select * from public.app_secret_status();   -- last4 = '7890'
--      select public.set_app_secret('embedding_api_key', 'dummy-key-abcdefghij');
--      select * from public.app_secret_status();   -- last4 = 'ghij' (update path)
--      select public.set_app_secret('embedding_api_key', null);
--      select * from public.app_secret_status();   -- 0 rows (delete path)
--      rollback;
