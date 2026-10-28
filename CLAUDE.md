# CLAUDE.md

RAG app with chat (default) and document ingestion interfaces. Config via env vars, no admin UI.

## Stack
- Frontend: React + Vite + Tailwind + shadcn/ui
- Backend: Python + FastAPI
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenAI (Module 1), OpenRouter (Module 2+)
- Observability: LangSmith

## Services
Start everything with `./scripts/start-services.sh` (Ctrl-C stops all of it).

| Service  | URL                    | Run manually                                                   |
|----------|------------------------|----------------------------------------------------------------|
| Backend  | http://localhost:8000  | `cd backend && venv/bin/uvicorn app.main:app --reload --port 8000` |
| Frontend | http://localhost:5173  | `cd frontend && npm run dev -- --port 5173 --strictPort`       |
| Supabase | hosted (no local run)  | URL/keys come from `backend/.env` and `frontend/.env`          |

- Requires `backend/.env` and `frontend/.env` (copy from the `.env.example` files)
- Creates `backend/venv` and runs `npm install` on first run if they're missing
- Fails fast if port 8000 or 5173 is busy. The frontend must stay on 5173 because backend CORS allows only `FRONTEND_ORIGIN`
- Backend health check: `curl localhost:8000/health` → `{"status":"ok"}`
- When adding a new service (e.g. a worker), add it to `scripts/start-services.sh` and to this table

## Rules
- Python backend must use a `venv` virtual environment
- No LangChain, no LangGraph - raw SDK calls only
- Use Pydantic for structured LLM outputs
- All tables need Row-Level Security - users only see their own data
- Stream chat responses via SSE
- Use Supabase Realtime for ingestion status updates
- Module 2+ uses stateless completions - store and send chat history yourself
- Ingestion is manual file upload only - no connectors or automated pipelines

## Planning
- Save all plans to `.agent/plans/` folder
- Naming convention: `{sequence}.{plan-name}.md` (e.g., `1.auth-setup.md`, `2.document-ingestion.md`)
- Plans should be detailed enough to execute without ambiguity
- Each task in the plan must include at least one validation test to verify it works
- Assess complexity and single-pass feasibility - can an agent realistically complete this in one go?
- Include a complexity indicator at the top of each plan:
  - ✅ **Simple** - Single-pass executable, low risk
  - ⚠️ **Medium** - May need iteration, some complexity
  - 🔴 **Complex** - Break into sub-plans before executing

## Development Flow
1. **Plan** - Create a detailed plan and save it to `.agent/plans/`
2. **Build** - Execute the plan to implement the feature
3. **Validate** - Test and verify the implementation works correctly. Use browser testing where applicable via an appropriate MCP
4. **Iterate** - Fix any issues found during validation

## Progress
Check PROGRESS.md for current module status. Update it as you complete tasks.

## Project Memory
Save things later sessions need to know (test credentials, decisions, gotchas) in `.claude/memory/`, which is committed to git. Don't use Claude's global per-user memory for this repo. Keep one file per topic and list each one in `.claude/memory/MEMORY.md`. Files imported below load into every session:

@.claude/memory/MEMORY.md
@.claude/memory/dev-test-accounts.md