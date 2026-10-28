-- Module 2.2: document ingestion. Uploaded files, their embedded chunks, and the private Storage bucket.
-- Only the backend (service role) writes chunks and changes document status, so there is no
-- insert/update policy on chunks and no update policy on documents.

create extension if not exists vector with schema extensions;

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  filename text not null,
  storage_path text not null unique,
  mime_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed')),
  error text,
  chunk_count int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents (id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding extensions.vector(1536) not null,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create index documents_user_id_created_at_idx on public.documents (user_id, created_at desc);
create index chunks_user_id_idx on public.chunks (user_id);
create index chunks_embedding_hnsw_idx on public.chunks using hnsw (embedding extensions.vector_cosine_ops);

-- Row-Level Security: users only see their own data.
alter table public.documents enable row level security;
alter table public.chunks enable row level security;

create policy "documents_select_own" on public.documents
  for select to authenticated using (user_id = (select auth.uid()));
create policy "documents_insert_own" on public.documents
  for insert to authenticated with check (user_id = (select auth.uid()));
create policy "documents_delete_own" on public.documents
  for delete to authenticated using (user_id = (select auth.uid()));

create policy "chunks_select_own" on public.chunks
  for select to authenticated using (user_id = (select auth.uid()));
create policy "chunks_delete_own" on public.chunks
  for delete to authenticated using (user_id = (select auth.uid()));

-- Live status updates for the Ingestion UI.
alter publication supabase_realtime add table public.documents;

-- Private Storage bucket; objects live under {user_id}/{document_id}/{filename}.
insert into storage.buckets (id, name, public, file_size_limit)
values ('documents', 'documents', false, 52428800)
on conflict (id) do nothing;

create policy "documents_storage_select_own" on storage.objects
  for select to authenticated using (
    bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
create policy "documents_storage_insert_own" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
create policy "documents_storage_delete_own" on storage.objects
  for delete to authenticated using (
    bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text
  );
