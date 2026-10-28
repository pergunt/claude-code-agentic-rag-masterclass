# CLAUDE.md

RAG app with chat (default) and document ingestion interfaces. Config via env vars, no admin UI.

## Stack
- Frontend: React + Vite + Tailwind + shadcn/ui
- Backend: Python + FastAPI
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenAI Responses API (Module 1); Chat Completions via any OpenAI-compatible endpoint, default OpenRouter (Module 2+, `LLM_BASE_URL` / `LLM_MODEL`); OpenAI for embeddings
- Observability: LangSmith

## Services
Start everything with `./scripts/start-services.sh` (Ctrl-C stops all of it).

If services may already be running (another terminal or another Claude session started them, or you're not sure), use `./scripts/restart-services.sh` instead. It kills every instance of this app's backend/frontend (any port, any session: `start-services.sh`, uvicorn plus its reload workers, npm/vite/esbuild), then starts fresh via `start-services.sh`. It only matches dev-server processes tied to this repo, so editors, shells and Claude sessions are left alone. If 8000/5173 is held by something outside this repo, it reports the PID and exits without killing it.

| Service  | URL                    | Run manually                                                   |
|----------|------------------------|----------------------------------------------------------------|
| Backend  | http://localhost:8000  | `cd backend && venv/bin/uvicorn app.main:app --reload --port 8000` |
| Frontend | http://localhost:5173  | `cd frontend && npm run dev -- --port 5173 --strictPort`       |
| Supabase | hosted (no local run)  | URL/keys come from `backend/.env` and `frontend/.env`          |

- Requires `backend/.env` and `frontend/.env` (copy from the `.env.example` files)
- Creates `backend/venv` and runs `npm install` on first run if they're missing
- Fails fast if port 8000 or 5173 is busy. The frontend must stay on 5173 because backend CORS allows only `FRONTEND_ORIGIN`
- Ingestion runs in-process via FastAPI BackgroundTasks (no worker); needs `SUPABASE_SERVICE_ROLE_KEY` in `backend/.env`
- Backend health check: `curl localhost:8000/health` → `{"status":"ok"}`
- When adding a new service (e.g. a worker), add it to `scripts/start-services.sh` and to this table
- Regression suite: `scripts/validate.sh quick|full [--only <ID prefix>] [--restart]`. It reuses running services or starts and stops its own. The report goes to `validation-report/latest/report.md`. `./scripts/restart-services.sh --stop` stops services without restarting them

## Rules
- Python backend must use a `venv` virtual environment
- No LangChain, no LangGraph - raw SDK calls only
- Use Pydantic for structured LLM outputs
- All tables need Row-Level Security - users only see their own data
- Stream chat responses via SSE
- Use Supabase Realtime for ingestion status updates
- Module 2+ uses stateless completions - store and send chat history yourself
- Ingestion is manual file upload only - no connectors or automated pipelines
- Service-role client only in `app/services/ingestion.py` (background work); request handlers use the user's JWT.
- Never read, print, source or edit `backend/.env` / `frontend/.env` (denied in `.claude/settings.json`). Check whether a key is set via `get_settings()` and print only `bool(...)`. Override a setting for one run with an env var on the command (env beats `.env`). Get curl test tokens from `eval "$(cd backend && venv/bin/python -m app.scripts.dev_tokens)"` (added in plan 2.1). Use the Read/Edit tools for `.env.example`.

## Planning
- Save all plans to `.agent/plans/` folder
- Naming convention: `{sequence}.{plan-name}.md` (e.g., `1.auth-setup.md`, `2.document-ingestion.md`)
- Plans should be detailed enough to execute without ambiguity
- Plans are executed by the `coder` subagent (Sonnet), not by the model that wrote them, so make every plan as detailed as possible. The coder should never have to guess or re-derive anything. For each task, spell out:
  - the exact files to create or edit, and the functions, components or SQL objects in them
  - names, signatures, types, env vars, and API/event shapes, plus code snippets wherever the shape matters
  - the expected behaviour, including edge cases and error handling
  - the conventions to follow (point to an existing file to copy)
  - what is out of scope
  - the validation commands and their expected output
- Each task in the plan must include at least one validation test to verify it works
- Assess complexity and single-pass feasibility - can an agent realistically complete this in one go?
- Include a complexity indicator at the top of each plan:
  - ✅ **Simple** - Single-pass executable, low risk
  - ⚠️ **Medium** - May need iteration, some complexity
  - 🔴 **Complex** - Break into sub-plans before executing
- Every plan that adds or changes a feature must include a **"Validation suite" task** (see below). A feature isn't done until it's in the suite.

## Validation suite (regression tests, keep it current)
`validation/FEATURES.md` lists every built feature with a stable ID (`AUTH-02`, `RET-08`, …) and its acceptance criteria. Tests carry the ID in their name, and `scripts/validate.sh` reports PASS/FAIL per ID. Details are in `validation/README.md` and plan `2.4.validation-suite.md`.

When you build a new feature or change an existing one, you **must** update the suite in the same build:
1. **Catalogue:**
   - Add a row to `validation/FEATURES.md` for each new user-visible behaviour, API contract or security rule: `| ID | Feature | Source plan | Tier | Acceptance criteria |`.
   - Use the next free number in the right section, or add a new section prefix for a new area.
   - Never renumber or reuse IDs. Mark removed features `Retired` instead of deleting them.
   - If behaviour changes, update the existing row's criteria.
2. **Tests,** named with the ID (`test_ING_15_…` in pytest, `test('ING-15 … @smoke', …)` in Playwright), at the cheapest tier that proves the criteria:
   - `unit`: pure logic in `backend/tests/`
   - `live`: API, RLS or SSE against running services in `backend/tests/live/`, using the `env`/`a`/`b`/`new_thread` fixtures
   - `llm`: anything that calls the chat model. Mark it `llm` and wrap behaviour assertions in `retry_llm`
   - `e2e`: browser flows in `frontend/e2e/`. Tag `@smoke` if it's cheap and has no LLM call
   - Every new table, RPC or storage path gets a cross-user isolation test (user B can't see user A's data).
3. **Test data:**
   - Use only the suite users `rag-test-val-a/b@example.com`, which are wiped every run.
   - Add new fixture files under `test-data/` and seed them in `app/scripts/validation_fixtures.py`.
4. **Run it:** `scripts/validate.sh full` (or `/validate`). Every ID must be PASS or PASS (flaky), with no UNCOVERED rows, before the feature counts as done.
   - Don't weaken an existing test or criterion to get a green run. If a change makes an old criterion wrong, update the row deliberately and say so in the build report.
   - If a new feature breaks an older ID, that's a regression to fix, not a test to delete.

## Development Flow
1. **Plan** - Create a detailed plan and save it to `.agent/plans/`
2. **Build** - Delegate the implementation to the `coder` subagent (`.claude/agents/coder.md`, Sonnet). Pass it the plan path, and say which tasks to do if the build is split. First sort the plan's tasks into dependency waves: independent tasks that touch different files run as parallel `coder` agents, and everything else runs in a valid order (see `/build`). Don't write the feature code in the main session.
3. **Review** - The main model (Opus) reviews what the coder did. Read the diff against the plan, check for missed tasks, deviations, bugs and convention breaks, then fix small issues directly or send them back to `coder` with precise instructions
4. **Validate** - Run the plan's own checks, then the full regression suite: `/validate full` (`scripts/validate.sh full`). Every ID in the report must be PASS or PASS (flaky), including the new feature's rows (see "Validation suite"). Use browser MCP testing for anything still unscripted
5. **Iterate** - Fix any issues found during validation (via `coder` for anything non-trivial), then review again
6. **Shut down** - When testing of a feature or module is finished, stop every process you started: the `start-services.sh` background task (or any manual uvicorn/vite), and close browser sessions (Playwright / Chrome MCP tabs). Then confirm nothing is left running: `lsof -iTCP:8000 -iTCP:5173 -sTCP:LISTEN` prints nothing, and `pgrep -fl "uvicorn app.main|vite"` finds no leftover processes

## Test credentials
Dev Supabase test users, all with password `TestPass123!` (details in `.claude/memory/dev-test-accounts.md`):
- `rag-test-a@example.com`: user A, owns `velmora-station.md`
- `rag-test-b@example.com`: user B, owns `b-recipes.md` (used for the cross-user RLS tests)
- `rag-test-c@example.com`, `rag-test-d@example.com`: created through the sign-up form
- `rag-test-val-a@example.com`, `rag-test-val-b@example.com`, `rag-test-val-c@example.com` (sign-in flows): owned by the validation suite, wiped and re-seeded every run. Don't use them for manual testing

For curl, `eval "$(cd backend && venv/bin/python -m app.scripts.dev_tokens)"` exports `TOKEN_A`/`TOKEN_B`/`USER_A_ID`/`USER_B_ID`. Scripts take `--as <email>`. New users follow the `rag-test-<x>@example.com` + `TestPass123!` pattern.

## Progress
Check PROGRESS.md for current module status. Update it as you complete tasks.

## Project Memory
Save things later sessions need to know (test credentials, decisions, gotchas) in `.claude/memory/`, which is committed to git. Don't use Claude's global per-user memory for this repo. Keep one file per topic and list each one in `.claude/memory/MEMORY.md`. Files imported below load into every session:

@.claude/memory/MEMORY.md
@.claude/memory/dev-test-accounts.md