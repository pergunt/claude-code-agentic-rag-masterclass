# Dev test accounts

Test users in the dev Supabase project (created 2026-10-28). All use the password `TestPass123!`:
- `rag-test-a@example.com` and `rag-test-b@example.com`: created via curl to `/auth/v1/signup`, used for the two-user RLS isolation test
- `rag-test-c@example.com`: created through the app's sign-up form in the browser
- `rag-test-d@example.com`: created through the sign-up form during the Module 1 regression pass (2026-10-28)

Email confirmation is disabled in the dev project, so any new `rag-test-<x>@example.com` + `TestPass123!` signs up instantly. Signing up an existing email returns "User already registered", so use sign-in for the accounts above.

- Use these for browser auth testing (Playwright / Chrome MCP) and API token tests. Don't invent other credentials.
- `eval "$(cd backend && venv/bin/python -m app.scripts.dev_tokens)"` signs in A and B and exports `TOKEN_A`/`TOKEN_B`/`USER_A_ID`/`USER_B_ID` for curl. Scripts take `--as <email>` (`check_retrieval`, `smoke_chat`).
- Test docs (2.3): A has `velmora-station.md` (several duplicate uploads plus a `test_file.txt`), B has `b-recipes.md` (from `test-data/ingestion/`).
- If you need a new user, follow the same email pattern and password, and add it to this file.
- If sign-in fails, the accounts may have been deleted or email confirmation re-enabled, so check Supabase → Authentication.
