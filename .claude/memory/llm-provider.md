# LLM provider (Module 2, plan 2.1)

Chat runs on the **Chat Completions API** via the raw `openai` SDK against any OpenAI-compatible base URL (default OpenRouter). Option A: the Responses API, OpenAI Conversations, `file_search`/vector store and `threads.openai_conversation_id` are gone (migration 0002).

## Env vars (backend/.env)
- `LLM_BASE_URL` (default `https://openrouter.ai/api/v1`), `LLM_API_KEY`, `LLM_MODEL` (default `openai/gpt-4.1-mini`, pick a tool-calling model for 2.3)
- `CHAT_SYSTEM_PROMPT` (optional, overrides the built-in tool-aware prompt in `services/prompts.py`), `CHAT_HISTORY_MAX_MESSAGES=20`, `CHAT_HISTORY_MAX_CHARS=24000`, `CHAT_MAX_OUTPUT_TOKENS=4096`
- `OPENAI_API_KEY` is only for embeddings (2.2)

## History window (`app/services/history.py`)
Newest 20 rows from `messages` → drop oldest until total content ≤ 24,000 chars → drop leading assistant messages. The current user message is always kept. Character budget, not tokens, because the model is provider-agnostic.

## Gotchas
- **Insert, then load:** `send_message` inserts the user message first and then calls `load_history`, so the DB is the single source of truth. A stopped partial reply is saved and appears in the next turn's history.
- **Empty `choices`:** the final usage-only chunk (`stream_options.include_usage`) has `choices == []`. Skip it.
- **OpenRouter `finish_reason: "error"`:** an in-band upstream failure. It becomes an `error` SSE event. Mid-stream `{"error": ...}` chunks raise `openai.APIError`.
- **402 without `max_tokens`:** OpenRouter reserves credit for the model's full output limit (65,536 for gpt-4.1-mini), so low-credit keys fail. `CHAT_MAX_OUTPUT_TOKENS` caps it.
- **LangSmith from a `python -c`:** `import app.config` first. It runs `load_dotenv`, otherwise `Client()` gets a 401.
- Curl test tokens: `eval "$(cd backend && venv/bin/python -m app.scripts.dev_tokens)"`.
