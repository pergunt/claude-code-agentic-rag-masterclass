# Document ingestion (Module 2, plan 2.2)

Upload (`POST /api/documents`, multipart) → private Storage bucket `documents` at `{user_id}/{document_id}/{safe_filename}` → `documents` row `pending` → FastAPI `BackgroundTasks` runs `ingestion.process_document`: processing → download → chunk (1500 chars / 200 overlap) → embed (`text-embedding-3-small`, 1536) → `chunks` → completed or failed. The UI updates over Supabase Realtime (`documents` is in the `supabase_realtime` publication).

## Service-role exception
- `create_service_client()` is used **only** in `app/services/ingestion.py` (background `process_document` and the startup sweep). Request handlers, including upload, list, get and delete, use the user's JWT under RLS.
- Why: a user JWT can expire mid-task and can't be refreshed there, and the sweep spans users.
- Users have no insert/update policy on `chunks` and no update policy on `documents`, so only the backend writes vectors and status. Service-role writes must set `user_id` explicitly, because `auth.uid()` is NULL.

## Restart sweep
- On startup the lifespan marks every `pending`/`processing` document `failed` ("interrupted by a server restart").
- A `uvicorn --reload` restart is graceful: it waits for background tasks, so the ingest finishes. The sweep only matters after a hard kill or crash. To test it: `kill -9` the worker mid-ingest, then `touch backend/app/main.py`.

## Test knobs and data
- `INGESTION_STAGE_DELAY_SECONDS=3 ./scripts/restart-services.sh` sleeps before processing and again before completed, so each status is visible in the browser. It's an env override, so don't edit `.env`.
- `EMBEDDING_MODEL=text-embedding-nope ./scripts/restart-services.sh` forces the failure path.
- Sample: `test-data/ingestion/velmora-station.md` gives 3 chunks (1265/1386/280). Facts for 2.3: the backup call sign is "Grey Reed", and samples must reach the cold room within 40 minutes.
- `app.scripts.check_chunker` and `app.scripts.smoke_embed` run offline checks.

## Gotchas
- **`python-multipart`** is required for `UploadFile`. `start-services.sh` now reinstalls requirements when `requirements.txt` is newer than `backend/venv/.requirements-installed`.
- **Storage as the user:** `create_user_client` sets `ClientOptions(headers={"Authorization": ...})`, because `postgrest.auth()` alone leaves Storage running as anon.
- **Realtime DELETE events** aren't RLS-filtered and carry only the primary key. The UI removes a row as soon as its own DELETE succeeds.
- **Timestamps:** API and Realtime format `updated_at` differently (`Z` vs `+00:00`). Compare parsed times, not strings.
- **Tracing:** `wrap_openai` doesn't trace `embeddings.create`, so `embed_texts` is `@traceable` (outputs summarised to count and dimensions).
- **Deleting stored files:** SQL `delete from storage.objects` is blocked. Use the Storage API.
