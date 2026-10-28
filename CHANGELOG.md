# Changelog

## 0.2 (2026-10-28)

Module 2: bring-your-own retrieval and memory. The app no longer depends on the OpenAI Responses API,
Conversations or vector stores. It ingests, stores and searches your documents itself.

### Features
- **Any OpenAI-compatible chat model**: replies stream via Chat Completions against `LLM_BASE_URL`
  (default OpenRouter, `openai/gpt-4.1-mini`). Chat history is rebuilt from the database each turn
  (last 20 messages within a character budget), so a stopped partial reply is part of the context.
- **Document ingestion**: drag-and-drop `.txt` / `.md` upload on a new Documents page. Files go to
  private Supabase Storage, then get chunked (1,500 characters, 200 overlap), embedded with
  `text-embedding-3-small` and stored in pgvector. Status moves Pending → Processing →
  Completed / Failed live via Supabase Realtime. Deleting a document removes its file and chunks.
- **Retrieval tool**: the model gets a `search_documents` tool and decides when to search. Up to 3
  search rounds per turn. Answers cite `(filename, chunk N)`, the UI shows
  "Searching documents for “…”" and Sources chips, and questions the documents don't cover get a
  clear "your documents don't cover this" answer.
- **Isolation**: documents, chunks, storage objects, messages and the `match_chunks` search all use
  Row-Level Security, so users only ever retrieve their own content.
- **Shared header**: Chat / Documents navigation, your email and Sign out on every signed-in page.
- **Observability**: LangSmith traces `chat_turn` → model call → `search_documents` → embedding +
  `match_chunks` retriever → model call, plus ingestion runs.
- **Dev tooling**: `pytest` suite, `check_retrieval` script for isolation and similarity calibration,
  `dev_tokens` for curl test tokens.

### Upgrade notes
- Apply migrations `0002`–`0005` in order. Add `LLM_*`, `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
  and the `RETRIEVAL_*` / `AGENT_MAX_TOOL_ROUNDS` settings from `backend/.env.example`.
- Existing threads lose their OpenAI conversation link; history now comes from stored messages.

### Known limitations
- Only `.txt` and `.md` uploads (PDF and other formats in a later module).
- Vector-only search: short queries for a fact inside a broad chunk can score near the 0.15 threshold
  and be missed. Hybrid keyword search and reranking come in a later module.
- Re-uploading the same file creates duplicate documents (no deduplication yet).

## 0.1 (2026-10-28)

First release: Module 1, the app shell with chat over your documents.

### Features
- **Auth**: email/password sign-up and sign-in with Supabase Auth. Sessions persist across reloads, and a
  deep link opened while signed out returns you to that page after sign-in. If the backend rejects the
  token (revoked or invalid), you are signed out and sent back to the login page.
- **Chat**: threads with create, rename and delete, stored in Supabase with Row-Level Security so users
  only see their own data. Replies stream over SSE from the OpenAI Responses API, use `file_search` over
  the configured vector store (with a "Searching documents…" indicator), and keep context across turns
  through OpenAI Conversations.
- **Stop button**: a red Stop button replaces Send while a reply streams. Stopping cancels the OpenAI
  stream and keeps (and saves) the partial reply.
- **Observability**: every chat turn is traced to LangSmith as a `chat_turn` run with thread and user
  metadata and the nested OpenAI call.
- **Dev scripts**: `scripts/start-services.sh` runs the backend and frontend together, and
  `scripts/restart-services.sh` kills any running instances (from any terminal or session) and starts
  fresh.

### Known limitations
- Deleting a thread waits on the OpenAI `conversations.delete` call (a few seconds).
- A stopped reply is saved in the app but not in the OpenAI conversation, so later turns don't see the
  partial answer.
- Ingestion (document upload) is not built yet. Retrieval uses an OpenAI vector store set up outside
  the app.
