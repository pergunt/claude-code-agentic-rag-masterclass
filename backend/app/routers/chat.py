import json
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from supabase import Client

from app.auth import CurrentUser, get_current_user
from app.db import create_user_client
from app.routers.threads import fetch_thread
from app.schemas import DEFAULT_THREAD_TITLE, ChatRequest
from app.services import llm

router = APIRouter(prefix="/api/threads", tags=["chat"])


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def chat_events(db: Client, thread: dict, user: CurrentUser, content: str) -> Iterator[str]:
    try:
        events = llm.stream_reply(
            thread["openai_conversation_id"],
            content,
            langsmith_extra={"metadata": {"thread_id": thread["id"], "user_id": user.id}},
        )
        for event in events:
            yield sse(event)
            if event["type"] == "done":
                db.table("messages").insert(
                    {"thread_id": thread["id"], "role": "assistant", "content": event["text"]}
                ).execute()
                thread_update = {"updated_at": datetime.now(UTC).isoformat()}
                if thread["title"] == DEFAULT_THREAD_TITLE:
                    thread_update["title"] = content.strip()[:60]
                db.table("threads").update(thread_update).eq("id", thread["id"]).execute()
    except Exception as exc:  # surface failures as an SSE event instead of a broken stream
        yield sse({"type": "error", "message": str(exc)})


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
    return StreamingResponse(
        chat_events(db, thread, user, body.content),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
