-- Module 2.3: vector search over the caller's own chunks. SECURITY INVOKER, so RLS on
-- chunks/documents applies; the explicit auth.uid() filter is defence in depth.
-- pgvector lives in the extensions schema (see 0003), hence extensions.vector below.

create or replace function public.match_chunks(
  query_embedding extensions.vector(1536),
  match_count int default 5,
  match_threshold float default 0.30
)
returns table (
  id uuid, document_id uuid, filename text, chunk_index int, content text, similarity float
)
language sql stable
security invoker
set search_path = public, extensions
-- If `select extversion from pg_extension where extname = 'vector'` is >= 0.8.0, you can add:
-- set hnsw.iterative_scan = relaxed_order
-- (keeps the HNSW scan from returning fewer than k rows when many users share the table;
-- irrelevant at dev scale, where the planner seq-scans anyway.)
as $$
  select c.id, c.document_id, d.filename, c.chunk_index, c.content,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.chunks c
  join public.documents d on d.id = c.document_id
  where c.user_id = (select auth.uid())
    and d.status = 'completed'
    and 1 - (c.embedding <=> query_embedding) >= match_threshold
  order by c.embedding <=> query_embedding
  limit least(greatest(match_count, 1), 50);
$$;

revoke execute on function public.match_chunks(extensions.vector, int, float) from public, anon;
grant execute on function public.match_chunks(extensions.vector, int, float) to authenticated;

-- Validate (SQL editor):
-- 1. Invoker, not definer (expect false):
--      select prosecdef from pg_proc where proname = 'match_chunks';
-- 2. anon cannot execute (expect false):
--      select has_function_privilege('anon', 'public.match_chunks(extensions.vector,int,float)', 'execute');
-- 3. Impersonation (one transaction); lists only that user's filenames. Repeat with B's uuid.
--    Get uuids from auth.users.
--      begin;
--      set local role authenticated;
--      set local request.jwt.claims = '{"sub":"<user A uuid>","role":"authenticated"}';
--      select distinct filename from match_chunks((select embedding from chunks limit 1), 50, -1);
--      rollback;
