from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_THREAD_TITLE = "New chat"


class UserOut(BaseModel):
    id: str
    email: str | None
    is_admin: bool = False


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


# --- Admin runtime settings (2.5.2) ---


class SettingField(BaseModel):
    value: str
    source: Literal["app", "env"]
    default: str


class SecretStatus(BaseModel):
    configured: bool
    source: Literal["app", "env"]
    last4: str | None = None


class AdminSettingsOut(BaseModel):
    llm_base_url: SettingField
    llm_model: SettingField
    embedding_base_url: SettingField
    embedding_model: SettingField
    llm_api_key: SecretStatus
    embedding_api_key: SecretStatus
    embedding_dimensions: int
    chunk_count: int
    embedding_locked: bool


class AdminSettingsIn(BaseModel):
    """Omitted field = unchanged (PUT) / env default (test); null = reset to the env default."""

    model_config = ConfigDict(extra="forbid")  # embedding_dimensions is fixed: a body with it is a 422

    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None

    @field_validator("llm_base_url", "embedding_base_url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().rstrip("/")
        parsed = urlparse(v)
        if not parsed.hostname or any(c.isspace() for c in v):
            raise ValueError("must be a valid URL")
        local = parsed.hostname in ("localhost", "127.0.0.1")
        if parsed.scheme == "https" or (parsed.scheme == "http" and local):
            return v
        raise ValueError("must start with https:// (http:// is allowed only for localhost)")

    @field_validator("llm_model", "embedding_model")
    @classmethod
    def _check_model(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v or len(v) > 200 or any(c.isspace() for c in v):
            raise ValueError("must be 1-200 characters with no whitespace")
        return v

    @field_validator("llm_api_key", "embedding_api_key")
    @classmethod
    def _check_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not 10 <= len(v) <= 400 or any(c.isspace() for c in v):
            raise ValueError("must be 10-400 characters with no whitespace")
        return v


class PartResult(BaseModel):
    ok: bool
    error: str | None = None
    model: str | None = None
    dimensions: int | None = None


class AdminTestOut(BaseModel):
    chat: PartResult
    embeddings: PartResult

