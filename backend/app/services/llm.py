import contextlib
import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI

from app.config import get_settings
from app.services.app_settings import RuntimeConfig, get_runtime_config
from app.services.prompts import DEFAULT_SYSTEM_PROMPT
from app.services.tool_calls import ToolCallAccumulator
from app.services.tools import TOOL_SCHEMAS, ToolContext, execute_tool

ChatEvent = dict[str, Any]  # public SSE events: delta / tool / done / error
ChatMessage = dict[str, Any]  # OpenAI chat message param: {"role", "content", ...}


@lru_cache(maxsize=8)
def get_chat_client(base_url: str, api_key: str) -> AsyncOpenAI:
    # Cached per (base_url, api_key) so an admin change takes effect without a restart.
    # wrap_openai traces each call to LangSmith; it's a no-op unless LANGSMITH_TRACING is set.
    # Async so a client disconnect cancels the provider stream right away.
    if not api_key:
        raise RuntimeError("LLM API key is not set")
    return wrap_openai(AsyncOpenAI(base_url=base_url, api_key=api_key))


def build_messages(history: list[ChatMessage]) -> list[ChatMessage]:
    """Prepend the system prompt (CHAT_SYSTEM_PROMPT or the built-in default) to the stored history."""
    prompt = get_settings().chat_system_prompt or DEFAULT_SYSTEM_PROMPT
    return [{"role": "system", "content": prompt}, *history]


def _final_event(events: list[ChatEvent]) -> ChatEvent | None:
    """Log the terminal done/error event as the run output instead of every delta."""
    return next((e for e in reversed(events) if e["type"] in ("done", "error")), None)


def cited_sources(sources: list[dict], text: str) -> list[dict]:
    """Sources whose filename the reply mentions, one per (document, chunk) with the best
    similarity, best first. Passages that were retrieved but not used don't become citations."""
    best: dict[tuple, dict] = {}
    for s in sources:
        if s["filename"] not in text:
            continue
        key = (s["document_id"], s["chunk_index"])
        if key not in best or s["similarity"] > best[key]["similarity"]:
            best[key] = s
    return sorted(best.values(), key=lambda s: s["similarity"], reverse=True)


def _query_of(raw_args: str) -> str | None:
    try:
        query = json.loads(raw_args).get("query")
    except (json.JSONDecodeError, AttributeError):
        return None
    return query if isinstance(query, str) else None


async def stream_completion(
    cfg: RuntimeConfig,
    messages: list[ChatMessage],
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
) -> AsyncIterator[ChatEvent]:
    """One streamed model call.

    Yields {"type": "delta", "delta"} events, then exactly one internal
    {"type": "completion", "finish_reason", "content", "tool_calls"} event (never sent to the client).
    """
    settings = get_settings()
    extra: dict[str, Any] = {}
    if "openrouter.ai" in cfg.llm_base_url:
        # Route only to providers that honour tools/tool_choice instead of silently dropping them.
        extra["extra_body"] = {"provider": {"require_parameters": True}}
    stream = await get_chat_client(cfg.llm_base_url, cfg.llm_api_key).chat.completions.create(
        model=cfg.llm_model,
        messages=messages,
        tools=tools or openai.omit,
        tool_choice=tool_choice if tools and tool_choice else openai.omit,
        # Without a cap OpenRouter reserves credit for the model's full output limit (402 on small keys).
        max_tokens=settings.chat_max_output_tokens,
        stream=True,
        stream_options={"include_usage": True},  # lets LangSmith record token counts
        **extra,
    )
    parts: list[str] = []
    acc = ToolCallAccumulator()
    finish_reason: str | None = None
    async with stream:  # closing it on cancellation closes the provider HTTP stream
        async for chunk in stream:
            if not chunk.choices:  # the final usage-only chunk has no choices
                continue
            choice = chunk.choices[0]
            acc.add(choice.delta.tool_calls)
            if choice.delta.content:
                parts.append(choice.delta.content)
                yield {"type": "delta", "delta": choice.delta.content}
            if choice.finish_reason:
                finish_reason = choice.finish_reason
    yield {
        "type": "completion",
        "finish_reason": finish_reason,
        "content": "".join(parts),
        "tool_calls": acc.calls(),
    }


@traceable(name="chat_turn", run_type="chain", reduce_fn=_final_event)
async def stream_reply(
    history: list[ChatMessage], ctx: ToolContext | None = None, cfg: RuntimeConfig | None = None
) -> AsyncIterator[ChatEvent]:
    """Stream a reply to the stored chat history as normalized events.

    Events: {"type": "delta", "delta"}, {"type": "tool", "name", "status", "query"?, "sources"?},
    {"type": "done", "text", "sources"}, {"type": "error", "message"}.
    With a ToolContext the model may call tools for up to AGENT_MAX_TOOL_ROUNDS rounds, then one
    last call with tool_choice="none" forces the answer. Cancelling the consumer (client
    disconnect) closes the provider stream.
    """
    cfg = cfg or get_runtime_config()
    messages = build_messages(history)
    max_rounds = get_settings().agent_max_tool_rounds
    text_parts: list[str] = []
    sources: list[dict] = []
    try:
        for round_no in range(max_rounds + 1):
            final = round_no == max_rounds
            round_text: list[str] = []
            completion: ChatEvent = {}
            # tools stay declared on the final call (tool_choice="none"): some providers reject
            # tool messages when no tools are declared.
            async with contextlib.aclosing(
                stream_completion(
                    cfg,
                    messages,
                    tools=TOOL_SCHEMAS if ctx else None,
                    tool_choice="none" if final else "auto",
                )
            ) as completions:
                async for event in completions:
                    if event["type"] == "delta":
                        if text_parts and not round_text:  # separate text from different rounds
                            text_parts.append("\n\n")
                            yield {"type": "delta", "delta": "\n\n"}
                        round_text.append(event["delta"])
                        text_parts.append(event["delta"])
                        yield event
                    else:
                        completion = event
            if completion.get("finish_reason") == "error":  # OpenRouter in-band upstream failure
                yield {"type": "error", "message": "The model provider returned an error"}
                return
            calls = completion.get("tool_calls") or []
            if not calls or ctx is None:  # decide on calls, not finish_reason: providers disagree
                break
            if final:
                if not text_parts:
                    fallback = "I couldn't complete the search in time. Please rephrase the question."
                    text_parts.append(fallback)
                    yield {"type": "delta", "delta": fallback}
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(round_text) or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments},
                        }
                        for c in calls
                    ],
                }
            )
            for call in calls:  # sequential: parallel calls are rare and cheap
                yield {
                    "type": "tool",
                    "name": call.name,
                    "status": "searching",
                    "query": _query_of(call.arguments),
                }
                result = await execute_tool(call.name, call.arguments, ctx)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result.content})
                sources += result.sources
                yield {
                    "type": "tool",
                    "name": call.name,
                    "status": "error" if result.error else "completed",
                    "sources": result.sources,
                }
        text = "".join(text_parts)
        yield {"type": "done", "text": text, "sources": cited_sources(sources, text)}
    except (openai.OpenAIError, RuntimeError) as exc:
        yield {"type": "error", "message": str(exc)}
