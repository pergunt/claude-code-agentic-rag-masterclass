# Validation suite

One command re-validates every built feature and writes a per-feature report. Acceptance criteria live in `validation/FEATURES.md`.

## Run

```
scripts/validate.sh quick|full [--only <regex>] [--restart]
```

- `--only <regex>`: run only tests whose name or ID matches
- `--restart`: force fresh services (otherwise healthy ones on :8000 and :5173 are reused; services the script started are stopped at exit)
- Agents: `/validate [quick|full|<ID regex>]` runs it, reads the report, triages each FAIL and shuts down
- Exit code is 0 only if nothing FAILed

## Tiers

| Tier | Runs |
|---|---|
| quick | static checks, `pytest -m "live and not llm"`, Playwright `--grep @smoke` |
| full | static checks (plus `npm run build`), `pytest -m live`, all Playwright specs, `check_traces` (SKIP if tracing is off) |

Static checks: `pytest -m "not live"`, `tsc -b`, lint vs `validation/lint-baseline.txt`, repo-rule tests.

## Test data

- Dedicated users `rag-test-val-a@example.com` and `rag-test-val-b@example.com` (password `TestPass123!`). Their threads and documents are wiped and re-seeded every run, so manual testing on `rag-test-a/b` never interferes.
- Failure paths run in-process (`httpx.ASGITransport`, monkeypatched dependency) or with Playwright route mocks, so no `.env` edits or restarts are needed.

## Report

`validation-report/latest/report.md` (symlink to `validation-report/<ts>/`): a table per catalogue section with status and evidence, plus `UNCOVERED` and `UNKNOWN` lists. Statuses are defined in `FEATURES.md`. Manual checks are in `validation/MANUAL.md`.

## LLM flaky policy

Protocol, data and security assertions are hard. Model-behaviour assertions are marked `llm` and get one retry in a fresh thread (Playwright: `retries: 1`). A pass on retry is `PASS (flaky)` and does not fail the run.

## Adding a feature

1. Add catalogue rows to `validation/FEATURES.md` in the plan that builds the feature. Pick a new ID (`[A-Z]{2,4}-NN`), never reuse one.
2. Name tests with the ID: pytest `test_ING_15_...`, Playwright `test('ING-15 ... @smoke', ...)`. Add `@smoke` or the `smoke` marker only for cheap, LLM-free checks.
3. Run `scripts/validate.sh quick --only ING-15`. The report flags catalogue IDs without a test as `UNCOVERED` and test IDs missing from the catalogue as `UNKNOWN`.
