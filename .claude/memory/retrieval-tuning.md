# Retrieval tuning (Module 2, plan 2.3)

`search_documents(query)` → `services/tools.py` → `retrieval.search_chunks` (embed + `match_chunks` RPC in one worker thread, user JWT so RLS applies) → top chunks formatted as `[i] filename, chunk N (similarity x)`.

## Defaults (backend/.env)
- `RETRIEVAL_MIN_SIMILARITY=0.15` (the plan said 0.30, but calibration showed that rejects real answers)
- `RETRIEVAL_TOP_K=5`, `AGENT_MAX_TOOL_ROUNDS=3` (then one final call with `tool_choice="none"`)

## Calibrated similarity ranges (text-embedding-3-small, CHUNK_SIZE=1500)
Measured 2026-10-28 on `test-data/ingestion/velmora-station.md`:
- Off-topic ("boiling point of tungsten", "sourdough"): 0.08–0.10
- Specific fact buried in a broad chunk ("backup call sign"): 0.15–0.23. That's borderline: terse queries can miss.
- Paraphrase / topical ("how long can samples wait", "radio procedures"): 0.41–0.52
- Noise depends on the question: a recipe question still scores 0.17–0.21 against Velmora chunks (above 0.15). The model ignores such passages and `cited_sources` keeps them out of the chips, so a higher threshold isn't needed. Expect weak passages in the tool result.
- Tiny junk docs (e.g. `test_file.txt`, "Test 123") score ~0.15–0.23 against almost anything, so they show up as noise.

Re-measure with `cd backend && venv/bin/python -m app.scripts.check_retrieval "<q>" --as rag-test-a@example.com [--as rag-test-b@example.com] --threshold -1`. It also checks that anon is denied.

## Gotchas
- User A has several duplicate uploads of `velmora-station.md`, so the same chunk can fill several of the top-5 slots (no dedup until Module 3 record management).
- Sources chips show only the sources whose filename the answer mentions (`llm.cited_sources`). Retrieved-but-unused passages aren't shown.
- Tool-capable model: on OpenRouter, `supported_parameters` must include `tools` and `tool_choice`. `stream_completion` sends `provider.require_parameters=true` for openrouter.ai base URLs.
- History stays text-only (D1): tool calls and results are never persisted, and `messages.sources` is display-only, never sent to the model.
- See [[llm-provider]] for the chat client and [[ingestion]] for the chunking side.
