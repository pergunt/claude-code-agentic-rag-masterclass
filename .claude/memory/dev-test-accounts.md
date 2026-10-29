# Dev test accounts

Test users in the dev Supabase project (created 2026-10-28). All use the password `TestPass123!`:
- `rag-test-a@example.com` and `rag-test-b@example.com`: created via curl to `/auth/v1/signup`, used for the two-user RLS isolation test
- `rag-test-c@example.com`: created through the app's sign-up form in the browser
- `rag-test-d@example.com`: created through the sign-up form during the Module 1 regression pass (2026-10-28)
- `rag-test-val-a@example.com`, `rag-test-val-b@example.com` and `rag-test-val-c@example.com` (sign-in/sign-out flows only; a sign-out revokes the user's sessions server-side, so it can't share an account with token-holding tests): owned by the validation suite (`scripts/validate.sh`, plan 2.4). Their threads and documents are wiped and re-seeded on every run; don't use them for manual testing

- `rag-test-val-admin@example.com` (plan 2.5): the suite's admin (`profiles.is_admin = true`, promoted by hand in SQL on 2026-10-28). Created by the fixtures setup, which also resets all admin settings overrides to null on every run. Don't use it for manual testing. To give another account Settings access: `update public.profiles set is_admin = true where email = '…';`

Email confirmation is disabled in the dev project, so any new `rag-test-<x>@example.com` + `TestPass123!` signs up instantly. Signing up an existing email returns "User already registered", so use sign-in for the accounts above.

- Use these for browser auth testing (Playwright / Chrome MCP) and API token tests. Don't invent other credentials.
- `eval "$(cd backend && venv/bin/python -m app.scripts.dev_tokens)"` signs in A and B and exports `TOKEN_A`/`TOKEN_B`/`USER_A_ID`/`USER_B_ID` for curl. Scripts take `--as <email>` (`check_retrieval`, `smoke_chat`).
- Test docs (2.3): A has `velmora-station.md` (several duplicate uploads plus a `test_file.txt`), B has `b-recipes.md` (from `test-data/ingestion/`).
- If you need a new user, follow the same email pattern and password, and add it to this file.
- If sign-in fails, the accounts may have been deleted or email confirmation re-enabled, so check Supabase → Authentication.
