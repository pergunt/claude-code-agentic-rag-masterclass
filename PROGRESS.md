# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability
- [x] Module 1: App Shell + Observability
  - [x] 1.1 Scaffold + Auth (`.agent/plans/1.1.scaffold-and-auth.md`)
  - [x] 1.2 Chat via Responses API + SSE (`.agent/plans/1.2.chat-responses-api.md`)
  - [x] 1.3 LangSmith tracing (`.agent/plans/1.3.langsmith-tracing.md`)
  - [x] 1.4 Stop streaming + quiet background load errors (`.agent/plans/1.4.stop-streaming-and-load-errors.md`)
  - Live-validated 2026-10-28: migration applied (anon sees 0 rows), `smoke_chat` streams with file_search, API CRUD + SSE via curl, cross-user RLS (404 on another user's thread), browser E2E (sign up, persist on reload, streaming, Conversations memory, rename, delete, sign out), LangSmith `chat_turn` runs with metadata and nested OpenAI call.
  - Known follow-ups: thread delete waits on the OpenAI `conversations.delete` call (a few seconds). A stopped reply is saved in the app but not in the OpenAI conversation, so later turns don't see the partial answer.
  - Auth flow tested 2026-10-28 (backend tokens + browser). Follow-ups fixed and browser-validated the same day: a backend 401 now clears the local session and redirects to `/login`; after login, a deep link (path + query) returns to the original URL instead of `/`.
  - Full Module 1 regression re-run 2026-10-28 after the auth fixes, all passing: `/api/me` 401 without/with bad token; anon REST sees 0 threads/messages; thread CRUD via curl; user B gets 404 on user A's thread (read/rename/delete); curl SSE streams `delta` events then `done` and both messages persist; `smoke_chat` triggers file_search on the verismo doc; browser sign-up, reload keeps session, doc question streams progressively with the "Searching documents" indicator, follow-up uses conversation memory, reload restores thread, rename persists, delete, sign out; LangSmith `chat_turn` run with thread/user metadata and nested OpenAI call. Services shut down afterwards.
  - 1.4 validated 2026-10-28: a red Stop button replaces Send while streaming; stopping freezes the text, saves the partial reply (survives reload, sets the thread title), and the OpenAI stream is cancelled at once (LangSmith `chat_turn` ends as cancelled); follow-ups after a stop work; curl disconnect also saves the partial. With the backend down, sign-in shows no error and sending shows "Can't reach the server…" instead of "Failed to fetch".

### Module 2: BYO Retrieval + Memory
- [-] Module 2: BYO Retrieval + Memory (`.agent/plans/2.module-2-overview.md`). Decisions: Option A (replace Responses API), OpenAI `text-embedding-3-small` embeddings, chat via OpenRouter. Build order 2.1 → 2.2 → 2.3.
  - [ ] 2.1 Chat Completions + self-managed history (`.agent/plans/2.1.chat-completions-migration.md`)
  - [ ] 2.2 Document ingestion + Realtime status (`.agent/plans/2.2.document-ingestion.md`)
  - [ ] 2.3 Retrieval tool + agent loop (`.agent/plans/2.3.retrieval-tool.md`)
