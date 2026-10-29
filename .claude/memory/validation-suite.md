# Validation suite (plan 2.4)

`scripts/validate.sh quick|full [--only <ID prefix>] [--restart]` re-checks every built feature. The report is at `validation-report/latest/report.md` (gitignored). For agents, `/validate` runs it and triages failures. The catalogue is `validation/FEATURES.md`: 61 IDs as of 2026-10-28 (after plan 2.5).

- **Timing:** full ≈ 3 min (static → live pytest → Playwright → LangSmith traces). Quick skips LLM tests and non-smoke e2e.
- **Services:** reuses running services (and warns that it's testing whatever code they were started from), otherwise starts its own and stops them at exit. `--restart` forces fresh services, and env overrides on the command reach them (e.g. `RETRIEVAL_MIN_SIMILARITY=0.99 scripts/validate.sh full --restart --only RET`).
- **`--only`:** takes `|`-separated ID prefixes (`RET`, `RET_02|CHAT`). In quick mode it only runs matching `@smoke` e2e tests; use `full --only` for any e2e test.
- **Users:**
  - `rag-test-val-a/b` are wiped and re-seeded (velmora / b-recipes) by `app.scripts.validation_fixtures setup` on every pytest session and every Playwright global setup.
  - `rag-test-val-c` is for sign-in/sign-out flows only.
  - Never use these for manual testing, and never run two suite runs at once: each run's setup wipes the other's data.
  - `rag-test-val-admin` is the admin (ADM/UI-03/04 tests). Admin tests reset every settings override to null in `finally`, and setup resets them too, so a crashed run can't leave the app misconfigured.
- **Gotcha: e2e sign-out races.** Wait for the page's first `/api/threads` response before signing out, or the in-flight request 401s and trips the console-error guard (UI-02).
- **Gotcha: sign-out revokes sessions.** Supabase sign-out revokes the user's sessions server-side, so a sign-out by any test invalidates other tests' tokens for that user (the 401s seen while building). Keep sign-out tests on val-c.
- **Flaky policy:**
  - LLM behaviour asserts use `retry_llm` (pytest), and Playwright runs with `retries: 1`. A pass on retry shows as `PASS (flaky)`.
  - CHAT-06 (Stop UI) is the most likely flake, because the provider sometimes stalls mid-stream.
- **Proven to catch breakage (2026-10-28):** threshold 0.99 → RET-02/RET-08 FAIL; `LLM_MODEL=nonexistent/model` → CHAT-01/02/03/06 FAIL with the provider error as evidence.
- **Faults are injected in-process** (`httpx.ASGITransport` + monkeypatch) for LLM/embedding failures (CHAT-04, ING-06), so no restart or `.env` edit is needed.
- **New features** must add catalogue rows and ID-named tests (CLAUDE.md "Validation suite").
