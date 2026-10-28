import contextlib
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI

from app.config import get_settings

ChatEvent = dict[str, Any]  # public SSE events: delta / tool / done / error
ChatMessage = dict[str, Any]  # OpenAI chat message param: {"role", "content", ...}


@lru_cache
def get_chat_client() -> AsyncOpenAI:
    # wrap_openai traces each call to LangSmith; it's a no-op unless LANGSMITH_TRACING is set.
    # Async so a client disconnect cancels the provider stream right away.
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    return wrap_openai(AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key))


def build_messages(history: list[ChatMessage]) -> list[ChatMessage]:
    """Prepend the optional system prompt to the stored history."""
    prompt = get_settings().chat_system_prompt
    return [{"role": "system", "content": prompt}, *history] if prompt else list(history)


def _final_event(events: list[ChatEvent]) -> ChatEvent | None:
    """Log the terminal done/error event as the run output instead of every delta."""
    return next((e for e in reversed(events) if e["type"] in ("done", "error")), None)


async def stream_completion(
    messages: list[ChatMessage], tools: list[dict] | None = None
) -> AsyncIterator[ChatEvent]:
    """One streamed model call.

    Yields {"type": "delta", "delta"} events, then exactly one internal
    {"type": "completion", "finish_reason", "content"} event (never sent to the client).
    """
    stream = await get_chat_client().chat.completions.create(
        model=get_settings().llm_model,
        messages=messages,
        tools=tools or openai.omit,
        # Without a cap OpenRouter reserves credit for the model's full output limit (402 on small keys).
        max_tokens=get_settings().chat_max_output_tokens,
        stream=True,
        stream_options={"include_usage": True},  # lets LangSmith record token counts
    )
    parts: list[str] = []
    finish_reason: str | None = None
    async with stream:  # closing it on cancellation closes the provider HTTP stream
        async for chunk in stream:
            if not chunk.choices:  # the final usage-only chunk has no choices
                continue
            choice = chunk.choices[0]
            # 2.3: collect choice.delta.tool_calls by index and add them to the completion event.
            if choice.delta.content:
                parts.append(choice.delta.content)
                yield {"type": "delta", "delta": choice.delta.content}
            if choice.finish_reason:
                finish_reason = choice.finish_reason
    yield {"type": "completion", "finish_reason": finish_reason, "content": "".join(parts)}


@traceable(name="chat_turn", run_type="chain", reduce_fn=_final_event)
async def stream_reply(history: list[ChatMessage]) -> AsyncIterator[ChatEvent]:
    """Stream a reply to the stored chat history as normalized events.

    Events: {"type": "delta", "delta"}, {"type": "tool", "name", "status"},
    {"type": "done", "text"}, {"type": "error", "message"}.
    Cancelling the consumer (client disconnect) closes the provider stream.
    """
    messages = build_messages(history)
    try:
        # 2.3: turn this single call into a bounded tool loop (see plan 2.1, "2.3 hook point").
        async with contextlib.aclosing(stream_completion(messages)) as completions:
            async for event in completions:
                if event["type"] == "delta":
                    yield event
                    continue
                if event["finish_reason"] == "error":  # OpenRouter in-band upstream failure
                    yield {"type": "error", "message": "The model provider returned an error"}
                    return
                yield {"type": "done", "text": event["content"]}
    except (openai.OpenAIError, RuntimeError) as exc:
        yield {"type": "error", "message": str(exc)}
