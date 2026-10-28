# Project memory

Shared, git-tracked notes for every Claude Code session on this repo. Add one file per topic and link it here.

- [Dev test accounts](dev-test-accounts.md): Supabase test users + password for auth/RLS testing
- [GitHub fork + releases](github-fork.md): pass `-R pergunt/...` to gh (defaults to upstream); release/tag conventions
- [LLM provider](llm-provider.md): Chat Completions via OpenRouter, env vars, history window, streaming/402 gotchas
- [Validation suite](validation-suite.md): `scripts/validate.sh` / `/validate`, tiers, suite users, flaky policy, sign-out-revokes-sessions gotcha
- [Retrieval tuning](retrieval-tuning.md): search_documents tool, calibrated similarity threshold (0.15), check_retrieval script, citation gotchas
- [Document ingestion](ingestion.md): upload → chunk → embed pipeline, service-role exception, restart sweep, test knobs, gotchas
