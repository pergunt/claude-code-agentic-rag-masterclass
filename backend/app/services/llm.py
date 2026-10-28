from collections.abc import Iterator
from functools import lru_cache
from typing import Any

import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.config import get_settings

ChatEvent = dict[str, Any]


@lru_cache
def get_client() -> OpenAI:
    # wrap_openai traces each OpenAI call to LangSmith; it's a no-op unless LANGSMITH_TRACING is set.
    return wrap_openai(OpenAI(api_key=get_settings().openai_api_key))


def create_conversation() -> str:
    return get_client().conversations.create().id


def delete_conversation(conversation_id: str) -> None:
    get_client().conversations.delete(conversation_id)


def _final_event(events: list[ChatEvent]) -> ChatEvent | None:
    """Log the terminal done/error event as the run output instead of every delta."""
    return next((e for e in reversed(events) if e["type"] in ("done", "error")), None)


@traceable(name="chat_turn", run_type="chain", reduce_fn=_final_event)
def stream_reply(conversation_id: str, text: str) -> Iterator[ChatEvent]:
    """Stream a reply within an OpenAI conversation as normalized events.

    Events: {"type": "delta", "delta"}, {"type": "tool", "name", "status"},
    {"type": "done", "text"}, {"type": "error", "message"}.
    """
    settings = get_settings()
    tools = (
        [{"type": "file_search", "vector_store_ids": [settings.openai_vector_store_id]}]
        if settings.openai_vector_store_id
        else openai.omit
    )
    parts: list[str] = []
    try:
        stream = get_client().responses.create(
            model=settings.openai_model,
            conversation=conversation_id,
            input=text,
            tools=tools,
            stream=True,
        )
        for event in stream:
            match event.type:
                case "response.output_text.delta":
                    parts.append(event.delta)
                    yield {"type": "delta", "delta": event.delta}
                case "response.file_search_call.searching":
                    yield {"type": "tool", "name": "file_search", "status": "searching"}
                case "response.file_search_call.completed":
                    yield {"type": "tool", "name": "file_search", "status": "completed"}
                case "error":
                    yield {"type": "error", "message": event.message}
                    return
                case "response.failed":
                    error = event.response.error
                    yield {"type": "error", "message": error.message if error else "Response failed"}
                    return
    except openai.OpenAIError as exc:
        yield {"type": "error", "message": str(exc)}
        return
    yield {"type": "done", "text": "".join(parts)}
