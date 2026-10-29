import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import anyio
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from supabase import Client

from app.auth import CurrentUser, get_current_user
from app.db import create_user_client
from app.routers.threads import fetch_thread
from app.schemas import DEFAULT_THREAD_TITLE, ChatRequest
from app.services import llm
from app.services.app_settings import RuntimeConfig, get_runtime_config
from app.services.history import load_history
from app.services.tools import ToolContext

router = APIRouter(prefix="/api/threads", tags=["chat"])


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def save_reply(
    db: Client, thread: dict, content: str, reply: str, sources: list[dict] | None = None
) -> None:
    db.table("messages").insert(
        {
            "thread_id": thread["id"],
            "role": "assistant",
            "content": reply,
            "sources": sources or None,  # display-only citations; never sent back to the model
        }
    ).execute()
    thread_update = {"updated_at": datetime.now(UTC).isoformat()}
    if thread["title"] == DEFAULT_THREAD_TITLE:
        thread_update["title"] = content.strip()[:60]
    db.table("threads").update(thread_update).eq("id", thread["id"]).execute()


async def chat_events(
    db: Client,
    thread: dict,
    user: CurrentUser,
    content: str,
    history: list[dict],
    cfg: RuntimeConfig,
) -> AsyncIterator[str]:
    parts: list[str] = []
    sources: list[dict] = []  # from completed search_documents calls
    ended = False  # set once the stream finished with done/error, i.e. the client didn't stop it
    try:
        events = llm.stream_reply(
            history,
            ToolContext(db=db, user_id=user.id),  # user-JWT client, so searches run under RLS
            cfg,
            langsmith_extra={
                "metadata": {
                    "thread_id": thread["id"],
                    "user_id": user.id,
                    "model": cfg.llm_model,
                }
            },
        )
        async for event in events:
            match event["type"]:
                case "delta":
                    parts.append(event["delta"])
                case "tool" if event["status"] == "completed":
                    sources.extend(event["sources"])
                case "done":
                    await run_in_threadpool(
                        save_reply, db, thread, content, event["text"], event["sources"]
                    )
                    ended = True
                case "error":
                    ended = True
            yield sse(event)
    except Exception as exc:  # surface failures as an SSE event instead of a broken stream
        ended = True
        yield sse({"type": "error", "message": str(exc)})
    finally:
        # The client stopped the reply (Stop button or disconnect): keep what was streamed so far.
        # Shielded because this runs while the request is being cancelled.
        if not ended and parts:
            with anyio.CancelScope(shield=True):
                reply = "".join(parts)
                await run_in_threadpool(
                    save_reply, db, thread, content, reply, llm.cited_sources(sources, reply)
                )


@router.post("/{thread_id}/messages")
def send_message(
    thread_id: str,
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    db = create_user_client(user.jwt)
    thread = fetch_thread(db, thread_id)
    db.table("messages").insert(
        {"thread_id": thread_id, "role": "user", "content": body.content}
    ).execute()
    cfg = get_runtime_config()  # once per request, so one turn never mixes two configs
    history = load_history(db, thread_id)  # after the insert, so it includes the new user message
    return StreamingResponse(
        chat_events(db, thread, user, body.content, history, cfg),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
