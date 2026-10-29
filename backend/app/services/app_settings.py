"""Runtime LLM/embedding configuration: admin overrides (app_settings + Vault) over the env defaults.

Second narrow service-role exception (with ingestion.py): decrypting the API keys needs get_app_secrets(),
which only service_role can call. Never log or return key values.
Precedence per field: DB override > env (.env) > code default. Cached for 30 s per process.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Literal

from app.config import get_settings
from app.db import create_service_client

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30.0
OVERRIDABLE_FIELDS = (
    "llm_base_url",
    "llm_api_key",
    "llm_model",
    "embedding_base_url",
    "embedding_api_key",
    "embedding_model",
)
Source = Literal["app", "env"]


@dataclass(frozen=True)
class RuntimeConfig:
    llm_base_url: str
    llm_api_key: str = field(repr=False)
    llm_model: str
    embedding_base_url: str
    embedding_api_key: str = field(repr=False)
    embedding_model: str
    embedding_dimensions: int  # always get_settings().embedding_dimensions, never overridden
    sources: dict[str, Source]


def env_defaults() -> dict[str, str]:
    """The env (.env / code default) value of each overridable field."""
    s = get_settings()
    return {
        "llm_base_url": s.llm_base_url,
        "llm_api_key": s.llm_api_key,
        "llm_model": s.llm_model,
        "embedding_base_url": s.embedding_base_url,
        "embedding_api_key": s.openai_api_key,
        "embedding_model": s.embedding_model,
    }


def _build(overrides: dict[str, str]) -> RuntimeConfig:
    values = env_defaults()
    sources: dict[str, Source] = {name: "env" for name in OVERRIDABLE_FIELDS}
    for name in OVERRIDABLE_FIELDS:
        value = overrides.get(name)
        if value:  # null / empty means "use the env default"
            values[name] = value
            sources[name] = "app"
    return RuntimeConfig(
        **values,
        embedding_dimensions=get_settings().embedding_dimensions,
        sources=sources,
    )


def _load_overrides() -> dict[str, str]:
    db = create_service_client()
    overrides: dict[str, str] = {}
    rows = db.table("app_settings").select("*").limit(1).execute().data
    if rows:
        for name in ("llm_base_url", "llm_model", "embedding_base_url", "embedding_model"):
            if rows[0].get(name):
                overrides[name] = rows[0][name]
    for row in db.rpc("get_app_secrets").execute().data or []:
        if row.get("decrypted_secret"):
            overrides[row["name"]] = row["decrypted_secret"]  # "llm_api_key" / "embedding_api_key"
    return overrides


_lock = threading.Lock()
_cached: RuntimeConfig | None = None
_cached_at = 0.0


def get_runtime_config() -> RuntimeConfig:
    """Effective config. Falls back to the env on any error, so chat never breaks on a settings failure."""
    global _cached, _cached_at
    with _lock:
        if _cached is not None and time.monotonic() - _cached_at < CACHE_TTL_SECONDS:
            return _cached
        try:
            config = _build(_load_overrides())
        except Exception as exc:  # missing service key, Supabase down, migration not applied yet
            logger.warning("Runtime settings unavailable, using env defaults: %s", type(exc).__name__)
            config = _build({})
        _cached, _cached_at = config, time.monotonic()
        return config


def invalidate() -> None:
    global _cached
    with _lock:
        _cached = None


def count_chunks() -> int:
    """Total chunks across all users (service role)."""
    res = create_service_client().table("chunks").select("id", count="exact", head=True).execute()
    return res.count or 0
