import asyncio
import dataclasses
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from supabase import Client

from app.auth import CurrentUser, get_db, require_admin
from app.schemas import AdminSettingsIn, AdminSettingsOut, AdminTestOut, PartResult
from app.services.app_settings import (
    RuntimeConfig,
    count_chunks,
    env_defaults,
    get_runtime_config,
    invalidate,
)
from app.services.embeddings import embed_texts
from app.services.llm import get_chat_client
from app.services.tools import TOOL_SCHEMAS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

TEST_TIMEOUT_SECONDS = 20
TEXT_FIELDS = ("llm_base_url", "llm_model", "embedding_base_url", "embedding_model")
KEY_FIELDS = ("llm_api_key", "embedding_api_key")


def _settings_out() -> dict:
    invalidate()  # never serve the 30 s cache here
    cfg = get_runtime_config()
    defaults = env_defaults()

    def field(name: str) -> dict:
        return {"value": getattr(cfg, name), "source": cfg.sources[name], "default": defaults[name]}

    def secret(name: str) -> dict:
        key = getattr(cfg, name)
        return {"configured": bool(key), "source": cfg.sources[name], "last4": key[-4:] if key else None}

    chunk_count = count_chunks()
    return {
        **{name: field(name) for name in TEXT_FIELDS},
        **{name: secret(name) for name in KEY_FIELDS},
        "embedding_dimensions": cfg.embedding_dimensions,
        "chunk_count": chunk_count,
        "embedding_locked": chunk_count > 0,
    }


@router.get("/settings", response_model=AdminSettingsOut)
def get_settings_view() -> dict:
    return _settings_out()


def _check_embedding_lock(submitted: dict) -> None:
    """409 if an embedding model/base URL change is submitted while chunks exist."""
    names = [n for n in ("embedding_model", "embedding_base_url") if n in submitted]
    if not names:
        return
    invalidate()
    cfg = get_runtime_config()
    defaults = env_defaults()
    changed = any(
        (submitted[n] if submitted[n] is not None else defaults[n]) != getattr(cfg, n) for n in names
    )
    if not changed:
        return
    n = count_chunks()
    if n > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Embedding settings are locked: {n} chunks exist. Delete all documents to change the embedding model.",
        )


@router.put("/settings", response_model=AdminSettingsOut)
def update_settings(
    body: AdminSettingsIn,
    user: CurrentUser = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    submitted = {name: getattr(body, name) for name in body.model_fields_set}
    _check_embedding_lock(submitted)
    payload: dict = {name: submitted[name] for name in TEXT_FIELDS if name in submitted}
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = user.id
    updated = db.table("app_settings").update(payload).eq("id", True).execute().data
    if not updated:  # RLS hid the row
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    for name in KEY_FIELDS:
        if name in submitted:
            db.rpc("set_app_secret", {"p_name": name, "p_value": submitted[name]}).execute()
    invalidate()
    return _settings_out()


def _redact(message: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message[:300]


async def _test_chat(cfg: RuntimeConfig) -> None:
    extra: dict = {}
    if "openrouter.ai" in cfg.llm_base_url:
        extra["extra_body"] = {"provider": {"require_parameters": True}}
    await asyncio.wait_for(
        get_chat_client(cfg.llm_base_url, cfg.llm_api_key).chat.completions.create(
            model=cfg.llm_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            tools=TOOL_SCHEMAS,
            **extra,
        ),
        TEST_TIMEOUT_SECONDS,
    )


@router.post("/settings/test", response_model=AdminTestOut)
async def test_settings(body: AdminSettingsIn) -> AdminTestOut:
    """Try the submitted (unsaved) values; omitted or null fields use the currently effective config."""
    current = get_runtime_config()
    defaults = env_defaults()
    submitted = {name: getattr(body, name) for name in body.model_fields_set}
    # A null means "env default" for that field; an omitted field keeps the current effective value.
    overrides = {name: (value if value is not None else defaults[name]) for name, value in submitted.items()}
    cfg = dataclasses.replace(current, **overrides)
    secrets = [cfg.llm_api_key, cfg.embedding_api_key, current.llm_api_key, current.embedding_api_key]

    chat = PartResult(ok=True, model=cfg.llm_model)
    try:
        await _test_chat(cfg)
    except Exception as exc:
        message = "Timed out" if isinstance(exc, asyncio.TimeoutError) else str(exc) or type(exc).__name__
        chat = PartResult(ok=False, model=cfg.llm_model, error=_redact(message, secrets))

    embeddings = PartResult(ok=True)
    try:
        vectors = await asyncio.wait_for(
            run_in_threadpool(embed_texts, ["ping"], cfg), TEST_TIMEOUT_SECONDS
        )
        embeddings = PartResult(ok=True, dimensions=len(vectors[0]))
    except Exception as exc:
        message = "Timed out" if isinstance(exc, asyncio.TimeoutError) else str(exc) or type(exc).__name__
        embeddings = PartResult(ok=False, error=_redact(message, secrets))
    return AdminTestOut(chat=chat, embeddings=embeddings)
