-- Module 2.3: display-only citations for assistant messages (filename/chunk/similarity per source).
-- Not sent back to the model; null for user messages and answers without retrieval.

alter table public.messages add column sources jsonb;
