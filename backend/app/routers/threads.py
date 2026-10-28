from fastapi import APIRouter, Depends, HTTPException, Response, status
from supabase import Client

from app.auth import get_db
from app.schemas import DEFAULT_THREAD_TITLE, MessageOut, ThreadCreate, ThreadOut, ThreadUpdate

router = APIRouter(prefix="/api/threads", tags=["threads"])


def fetch_thread(db: Client, thread_id: str) -> dict:
    """Return the thread row, or 404. RLS hides other users' threads."""
    rows = db.table("threads").select("*").eq("id", thread_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    return rows[0]


@router.get("", response_model=list[ThreadOut])
def list_threads(db: Client = Depends(get_db)) -> list[dict]:
    return db.table("threads").select("*").order("updated_at", desc=True).execute().data


@router.post("", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
def create_thread(body: ThreadCreate, db: Client = Depends(get_db)) -> dict:
    row = {"title": body.title or DEFAULT_THREAD_TITLE}
    return db.table("threads").insert(row).execute().data[0]


@router.patch("/{thread_id}", response_model=ThreadOut)
def update_thread(thread_id: str, body: ThreadUpdate, db: Client = Depends(get_db)) -> dict:
    rows = db.table("threads").update({"title": body.title}).eq("id", thread_id).execute().data
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    return rows[0]


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: str, db: Client = Depends(get_db)) -> Response:
    rows = db.table("threads").delete().eq("id", thread_id).execute().data
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{thread_id}/messages", response_model=list[MessageOut])
def list_messages(thread_id: str, db: Client = Depends(get_db)) -> list[dict]:
    fetch_thread(db, thread_id)
    return (
        db.table("messages")
        .select("*")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
        .data
    )
