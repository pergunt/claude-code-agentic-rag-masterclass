# Changelog

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
