-- Module 1: chat threads and mirrored messages.
-- OpenAI's Conversations API holds the model-side history; `messages` mirrors it for fast UI rendering.

create table public.threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title text not null default 'New chat',
  openai_conversation_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.threads (id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create index threads_user_id_updated_at_idx on public.threads (user_id, updated_at desc);
create index messages_thread_id_created_at_idx on public.messages (thread_id, created_at);

-- Row-Level Security: users only see their own data.
alter table public.threads enable row level security;
alter table public.messages enable row level security;

create policy "threads_select_own" on public.threads
  for select to authenticated using (user_id = (select auth.uid()));
create policy "threads_insert_own" on public.threads
  for insert to authenticated with check (user_id = (select auth.uid()));
create policy "threads_update_own" on public.threads
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy "threads_delete_own" on public.threads
  for delete to authenticated using (user_id = (select auth.uid()));

create policy "messages_select_own" on public.messages
  for select to authenticated using (user_id = (select auth.uid()));
-- A message may only be attached to a thread the user owns.
create policy "messages_insert_own" on public.messages
  for insert to authenticated with check (
    user_id = (select auth.uid())
    and exists (select 1 from public.threads t where t.id = thread_id and t.user_id = (select auth.uid()))
  );
create policy "messages_update_own" on public.messages
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy "messages_delete_own" on public.messages
  for delete to authenticated using (user_id = (select auth.uid()));
