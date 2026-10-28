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
  - Live-validated 2026-10-28: migration applied (anon sees 0 rows), `smoke_chat` streams with file_search, API CRUD + SSE via curl, cross-user RLS (404 on another user's thread), browser E2E (sign up, persist on reload, streaming, Conversations memory, rename, delete, sign out), LangSmith `chat_turn` runs with metadata and nested OpenAI call.
  - Known follow-ups: assistant message is not saved if the client disconnects mid-stream; thread delete waits on the OpenAI `conversations.delete` call (a few seconds).
  - Auth flow tested 2026-10-28 (backend tokens + browser). Follow-ups: a backend 401 (revoked or invalid token that hasn't expired) leaves the UI "signed in" with an error instead of signing out; after login, a deep link redirects to `/` instead of the original URL.
