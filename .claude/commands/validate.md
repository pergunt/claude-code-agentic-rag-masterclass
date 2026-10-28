---
description: Run the validation suite and triage failures
argument-hint: [quick|full] [--only <ID prefixes>] [--restart]
---

# Validate

Arguments: `$ARGUMENTS` (default: `full`)

Runs the scripted suite (pytest + Playwright + LangSmith trace checks) and triages the result. Don't hand-test; the scripts do that. Catalogue: `validation/FEATURES.md`. Details: `validation/README.md`.

## Process

1. **Run** `scripts/validate.sh $ARGUMENTS` (use `full` if no arguments) as a background Bash task and wait for it to exit. Don't poll its output. `--only` takes `|`-separated ID prefixes, e.g. `RET` or `RET-02|CHAT`.
   - Running services on :8000/:5173 are reused (the run warns that it tests the code they were started from). Use `--restart` after backend code or env changes.
   - Concurrent runs wipe each other's test data (the val users are re-seeded on every run). Make sure no other validation run is active.

2. **Read** `validation-report/latest/report.md`: totals line, then the tables per section.
   - Green means every row is `PASS` or `PASS (flaky)` (`SKIP` is fine; `NOT RUN` is expected for tiers the mode excludes).
   - `UNCOVERED` is a failure: a catalogue ID has no test, or its tier crashed. Check the `*.log` files in the report dir.

3. **Triage each FAIL / UNCOVERED.** Evidence sources, all under `validation-report/latest/`:
   - pytest: `junit-unit.xml`, `junit-live.xml`, plus `unit.log` / `live.log`
   - Playwright: `playwright.json`, `playwright.log`, `playwright-artifacts/*/error-context.md`, screenshots (look at them)
   - traces: `traces.json`, `traces.log`; static: `static/*.status`, `tsc.log`, `lint.log`, `build.log`; services: `services.log`

   Classify each as:
   - **regression**: the app broke. Name the likely file or commit (`git log -5 -- <path>`).
   - **flaky LLM**: model behaviour only. Re-run once with `scripts/validate.sh full --only <ID>`. If it still fails, treat it as a regression or test bug.
   - **environment**: missing key, OpenRouter 402, Supabase down, services not up, LangSmith unreachable.
   - **test bug**: the test is wrong against the written acceptance criteria.

4. **Never weaken a test or an acceptance criterion** to make it pass without telling the user explicitly. Fixing a real test bug is fine; say what changed.

5. **Report** a table: ID, classification, evidence (one line), suggested fix. Add the totals line and the report path.

6. **Shut down** (CLAUDE.md step 6). The runner stops services it started itself. If it reused services that were already running, leave them as found unless the user asked otherwise. Close any browser sessions you opened, and confirm with `lsof -iTCP:8000 -iTCP:5173 -sTCP:LISTEN` and `pgrep -fl "uvicorn app.main|vite"` that nothing you started is left.
