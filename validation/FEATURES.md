# Feature catalogue

Acceptance criteria for every built feature. `scripts/validate.sh` runs the tests that carry these IDs, and the report joins results against this file.

IDs are stable: never renumber or reuse an ID. A retired feature stays in the table with its status marked `Retired` instead of being deleted. New plans add their own rows (see `validation/README.md`).

## Legend

Tiers:
- `unit`: pytest without live services (`-m "not live"`)
- `live`: pytest against the running backend and hosted Supabase (`-m live`)
- `llm`: depends on model behaviour; one retry, a pass on retry is `PASS (flaky)`
- `e2e`: Playwright browser spec
- `traces`: LangSmith trace check (`app.scripts.check_traces`, full only)
- `smoke`: also runs in `quick` mode

Statuses: `PASS`, `PASS (flaky)`, `FAIL`, `SKIP`, `NOT RUN`, `UNCOVERED` (catalogue ID with no test).

## Static

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| STA-01 | Backend unit tests | 2.4 | unit | `pytest -m "not live"` exits 0 (tool calls, tools, agent loop, history, chunker, decode, sweep, repo rules) |
| STA-02 | Frontend types/build | 2.4 | unit | `npx tsc -b` exits 0. Full tier only: `npm run build` exits 0 |
| STA-03 | Lint | 2.4 | unit | `npm run lint`: 0 errors, warnings ≤ `validation/lint-baseline.txt` (5) |
| STA-04 | Repo rules (CLAUDE.md) | 2.4 | unit | No Responses/Conversations remnants (`conversations\.`, `responses\.create`, `file_search`, `openai_conversation_id`); no `langchain`/`langgraph` in `requirements.txt` or `package.json`; `create_service_client(` called only in `services/ingestion.py`, `services/app_settings.py` and `db.py`; no tracked `.env` files (`git ls-files`); every `create table public.X` in `supabase/migrations/*.sql` has a matching `enable row level security` |

## Auth (1.1)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| AUTH-01 | Health | 1.1 | live, smoke | `GET /health` → 200 `{"status":"ok"}` |
| AUTH-02 | API auth | 1.1 | live, smoke | `/api/me`: no token → 401, garbage token → 401, valid token → 200 with `id` = user id and `email` |
| AUTH-03 | Sign-in UI | 1.1 | e2e, smoke | Valid credentials → `/` with the user's email in the header. Wrong password → error text shown, still on `/login` |
| AUTH-04 | Session + sign out | 1.1 | e2e, smoke | Reload keeps the session. Sign out → `/login`, and visiting `/` then redirects to `/login` |
| AUTH-05 | Deep link | 1.1 | e2e | Signed out, open `/documents` → `/login` → after sign-in, lands on `/documents` |
| AUTH-06 | Backend 401 | 1.1 | e2e | When the API answers 401 (route-mocked `/api/threads`), the session is cleared and the app goes to `/login` |
| AUTH-07 | Sign-up form | 1.1 | e2e | Signing up with the existing val-a email shows the "already registered" error (form wired to Supabase, no new user created) |

## Threads (1.2, 2.1)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| THR-01 | Thread CRUD | 1.2, 2.1 | live | Create → 201 in < 1.5 s, no `openai_conversation_id` key. It appears in the list (newest `updated_at` first). PATCH title → 200 and persisted. DELETE → 204. Then messages → 404, and a second DELETE → 404 |
| THR-02 | Input validation | 1.2 | live | PATCH `""` title → 422, 201-char title → 422, POST message `""` → 422 |
| THR-03 | Cross-user isolation | 1.2 | live | B gets 404 on A's thread for GET messages, PATCH, DELETE and POST messages. A's thread and messages are unchanged afterwards |
| THR-04 | Anon REST blocked | 2.2 | live, smoke | Anon key `GET /rest/v1/{threads,messages,documents,chunks}?select=id` → `[]` |
| THR-05 | Threads UI | 1.2 | e2e, llm | First message creates a thread (`/t/<id>`) titled with the first message (≤ 60 chars). Sidebar rename persists across reload. Delete removes it |

## Chat (1.2, 1.4, 2.1)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| CHAT-01 | SSE streaming | 1.2, 2.1 | live, llm | `text/event-stream`. ≥ 2 `delta` events, then exactly one `done` whose `text` equals the joined deltas. User and assistant rows persisted with that content |
| CHAT-02 | Stateless memory | 2.1 | live, llm | "My favourite city is Lisbon. Reply briefly." then "Which city did I mention?" → answer contains "Lisbon" |
| CHAT-03 | Disconnect saves partial | 1.4 | live, llm | Close the stream after ≥ 3 deltas of a long answer. Within 5 s an assistant row with non-empty content exists, and the next turn in that thread ends in `done` |
| CHAT-04 | Provider error | 2.1 | live | Injected `get_chat_client` failure → SSE `error` event, the stream ends cleanly, the user row is stored and no assistant row is (in-process) |
| CHAT-05 | History window | 2.1 | unit | `trim_history`: keeps the last N, respects the char budget, starts on a user turn, always keeps the newest message even if oversize |
| CHAT-06 | Streaming UI + Stop | 1.4 | e2e, llm | A long prompt shows the `Stop` button. Assistant text grows across ≥ 2 samples (progressive). Stop → Send returns and the partial stays. Reload → the partial is still shown. A follow-up gets a reply |
| CHAT-07 | Network error UI | 1.2 | e2e | With `localhost:8000/**` aborted via route, sending shows "Can't reach the server…" |
| CHAT-08 | Composer | 1.2 | e2e, smoke | Send is disabled when empty. Shift+Enter inserts a newline without sending. Enter sends. Uses a route-mocked SSE response, so no LLM. |

## Ingestion (2.2)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| ING-01 | Pipeline | 2.2 | live | `.md` upload → 201 `pending` → `completed` within 60 s, `error` null. `chunk_count` = number of chunk rows. `chunk_index` = 0..n-1. Each content ≤ `CHUNK_SIZE`. Each embedding has 1536 dims (REST under the owner's JWT) |
| ING-02 | Storage | 2.2 | live | The owner can download the object at `storage_path`, byte-identical to the upload |
| ING-03 | Upload validation | 2.2 | live, smoke | `.pdf` → 415, empty `.txt` → 400, > `MAX_UPLOAD_BYTES` → 413, non-UTF-8 (`\xff\xfe\x00bad`) → 415, no token → 401 |
| ING-04 | Cross-user isolation | 2.2 | live | B: GET and DELETE on A's doc → 404 (it still exists for A). B REST `documents`/`chunks` for that id → `[]`. B Storage GET of A's path fails (400/404). B upload into A's folder is rejected (400/403) |
| ING-05 | Least privilege | 2.2 | live | A: REST insert into `chunks` is rejected. A: REST PATCH `documents` status with `Prefer: return=representation` → `[]` and the status is unchanged |
| ING-06 | Failure path | 2.2 | live | Injected `embed_texts` failure (in-process) → `failed`, `error` contains the injected message, `chunk_count` 0, no chunk rows (in-process) |
| ING-07 | Interrupted sweep | 2.2 | unit | `fail_interrupted_documents()` on a fake client updates only `pending`/`processing` rows to `failed` with `INTERRUPTED_MESSAGE`, and is a no-op without a service key |
| ING-08 | Delete | 2.2 | live | 204. Then GET → 404, chunks → `[]`, the Storage object is gone, and `match_chunks` no longer returns its content |
| ING-09 | Chunker + decoding | 2.2 | unit | Chunks ≤ size with overlap, empty text → `[]`, BOM stripped, invalid bytes / NUL → `UnsupportedFile` |
| ING-10 | Realtime status UI | 2.2 | e2e | File-picker upload: the row appears and reaches "Completed" without a reload. Exactly 1 `POST /api/documents` and no `GET /api/documents` after it (no polling) |
| ING-11 | Drop + client rejection | 2.2 | e2e | A dispatched drop of `drop-test.md` on `[data-testid=upload-dropzone]` → Completed. A dropped `x.pdf` shows "unsupported file type" and sends no request |
| ING-12 | Failed display | 2.2 | e2e | A failed document shows the Failed status and its error text (route-mocked list response) |
| ING-13 | Delete + persistence UI | 2.2 | e2e | Rows survive a reload. "Delete document" removes the row, and it stays gone after reload |
| ING-14 | Realtime isolation | 2.2 | e2e | With B's `/documents` open, A's upload (via API) never appears in B's list |

## Retrieval (2.3)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| RET-01 | `match_chunks` RLS | 2.3 | live, smoke | With `--threshold -1`, A's results are only A's files and B's only B's. Anon RPC → error code `42501` |
| RET-02 | Grounded answer | 2.3 | live, llm | "How long can samples wait before the cold room?" (as A): `tool searching` with non-empty `query` → `tool completed` with ≥ 1 source, all `velmora-station.md` → deltas → `done`. The text contains "40" and "velmora-station.md". `done.sources` is non-empty, all velmora. Exactly 2 new rows, and the assistant row's `sources` is non-empty |
| RET-03 | Not covered | 2.3 | live, llm | "What does my document say about the parking policy?" → `done.sources == []`, the text has no "chunk" citation, and the stored `sources` is null |
| RET-04 | No search for small talk | 2.3 | live, llm | "hi" → no `tool` events |
| RET-05 | Cross-user retrieval | 2.3 | live, llm | B asks RET-02's question → no source with A's filename or document id |
| RET-06 | Stop during search | 2.3 | live, llm | Disconnect right after `searching` → no orphaned state: the next turn in the thread ends in `done` (no 400) |
| RET-07 | Loop bounds + bad args | 2.3 | unit | Existing unit tests: max rounds then `tool_choice="none"`, invalid args fed back, accumulator cases, `cited_sources` |
| RET-08 | Retrieval UI | 2.3 | e2e, llm | "Searching documents for “…”" appears. The answer shows a Sources chip `velmora-station.md` whose title matches `chunks .* · best similarity 0\.\d\d`. The chip persists after reload. The not-covered answer has no chip |

## Layout (2.2.1)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| UI-01 | App sidebar | 2.2.1, 2.5.1 | e2e, smoke | `/login` has no sidebar. `/`, `/t/<id>` and `/documents` show the left sidebar with the Chat/Documents nav (right one active) and the account menu button (containing the email). `scrollHeight <= innerHeight` on `/` and `/documents`. The composer is visible |
| UI-02 | Account menu | 2.5.1 | e2e, smoke | Initials button at the bottom-left of the sidebar on `/` and `/documents`; its menu shows the email and Sign out. Settings is absent for a non-admin (val-a) and present for an admin (val-admin), opening a dialog titled "Settings". Sign out returns to `/login` |
| UI-03 | Settings dialog | 2.5.3 | e2e | Settings is hidden for val-a. As val-admin the dialog shows the sections "LLM configuration" and "Embedding configuration" with source badges. Both API key inputs have `type="password"` and an empty value; Dimensions is disabled and shows 1536. A successful Save closes the dialog; a rejected Save (e.g. an `ftp://` base URL) keeps it open with the field error. Setting the LLM model name to its current effective value and saving persists after reload with the `App` badge; Reset to default shows the `Default` badge. A key field never shows more than `•••• last4`. All settings are reset afterwards. With the suite's seeded chunks, Embedding model name and Embedding base URL are disabled with a lock notice that gives the chunk count and explains why (vectors from another model can't be compared with the stored ones); the Embedding API key input stays enabled |
| UI-04 | Test connection | 2.5.3 | e2e | Test connection in the Settings dialog shows a success mark for both chat and embeddings with the effective config |

## Admin (2.5)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| ADM-01 | Profiles RLS | 2.5.1 | live | A user reads only their own `profiles` row. A REST PATCH setting `is_admin=true` on their own row changes nothing (no rows returned; re-read is still false). Anon select returns `[]` |
| ADM-02 | `/api/me.is_admin` | 2.5.1 | live | `GET /api/me` returns `is_admin` false for val-a and true for val-admin |
| ADM-03 | Admin-only settings API | 2.5.2 | live | val-a gets 403 on every `/api/admin/*` route (GET/PUT settings, POST settings/test). val-a REST `app_settings` returns `[]`; val-a `rpc set_app_secret` errors; any JWT (user or admin) calling `rpc get_app_secrets` gets `42501` |
| ADM-04 | Secrets never leave the server | 2.5.2 | live | After val-admin PUTs a dummy `embedding_api_key`, GET shows `{configured: true, source: "app", last4}` with the matching last 4 characters, and no response body contains the full key. Resetting to `null` returns the source to `env` |
| ADM-05 | Override, reset and validation | 2.5.2 | live, llm | PUT `llm_model` and `embedding_base_url` set to their current effective values: GET shows them with source `app`, and a RET-style chat as val-a still streams and cites. PUT `null` for both returns the env values with source `env`. PUT with `embedding_dimensions` is 422 (`extra="forbid"`); an `http://` non-localhost URL, a model with whitespace, or a key outside 10-400 chars / with whitespace is 422 (also covered in-process, unit) |
| ADM-06 | Bad model surfaces cleanly | 2.5.2 | live, llm | PUT `llm_model="nonexistent/model"`: a chat turn ends with an `error` SSE event, not a traceback. After reset to `null`, chat works again |
| ADM-07 | Test connection | 2.5.2 | live, llm | POST `/api/admin/settings/test` with `{}` gives `chat.ok` true and `embeddings.ok` true with `dimensions` 1536. A bogus `llm_api_key` in the body gives `chat.ok` false with an error that does not contain the key. Nothing is saved (GET unchanged) |
| ADM-08 | Embedding settings lock | 2.5.2 | unit, live | `process_document` writes the effective `embedding_model` on completion (unit). Admin GET returns `chunk_count` (int) and `embedding_locked` (= chunk_count > 0). While chunks exist, PUT changing `embedding_model` or `embedding_base_url` (null resolves to the env default) to a different effective value returns 409 `Embedding settings are locked: N chunks exist. Delete all documents to change the embedding model.` and writes nothing; same-value submissions and `embedding_api_key` changes are allowed; with 0 chunks changes are allowed; `/settings/test` is unrestricted. Live: with the suite's seeded chunks, GET shows locked, a model change and a base-URL change are 409 with settings unchanged, and PUT of both current values is 200 |
| ADM-09 | Runtime config precedence + env fallback | 2.5.2 | unit | get_runtime_config() merges admin overrides (app_settings + Vault secrets) over the env: a non-empty override wins with source "app"; null/empty stays on the env default with source "env". If the service client or Supabase fails it logs a warning and falls back to all-env values without raising. Cached 30 s; invalidate() clears it. API key values never appear in the RuntimeConfig repr or in logs. |

## Observability (1.3, 2.2, 2.3)

| ID | Feature | Source | Tier | Acceptance criteria |
|---|---|---|---|---|
| OBS-01 | Chat trace tree | 1.3, 2.3 | traces | A `chat_turn` root since the run started, for val-a's user id, has metadata `thread_id`/`user_id`/`model`, ≥ 2 `llm` children, and a `search_documents` [tool] child with nested `embed_texts` [embedding] and `match_chunks` [retriever]. SKIP if tracing is off. |
| OBS-02 | Ingestion trace | 2.2 | traces | An `ingest_document` run since the run started has `document_id` and `chunk_count` metadata and a nested `embed_texts` |
