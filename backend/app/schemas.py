from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_THREAD_TITLE = "New chat"


class UserOut(BaseModel):
    id: str
    email: str | None


class ThreadOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ThreadUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SourceOut(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    similarity: float


class MessageOut(BaseModel):
    id: str
    thread_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list[SourceOut] | None = None


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


DocumentStatus = Literal["pending", "processing", "completed", "failed"]


class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
