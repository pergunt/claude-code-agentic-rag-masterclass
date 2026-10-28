-- Module 2 (Option A): chat history lives in public.messages and is sent with every
-- Chat Completions request, so the link to OpenAI's Conversations API is gone.
alter table public.threads drop column if exists openai_conversation_id;
