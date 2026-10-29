from functools import lru_cache
from itertools import batched

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.services.app_settings import RuntimeConfig, get_runtime_config

BATCH_SIZE = 100


@lru_cache(maxsize=8)
def get_client(base_url: str, api_key: str) -> OpenAI:
    # Separate from llm.py on purpose: chat and embeddings can use different providers.
    # Cached per (base_url, api_key) so an admin change takes effect without a restart.
    if not api_key:
        raise RuntimeError("Embedding API key is not set (OPENAI_API_KEY)")
    return wrap_openai(OpenAI(base_url=base_url, api_key=api_key))


def _summarize_vectors(vectors: list[list[float]]) -> dict:
    # Keep traces small: record the shape, not 1536 floats per chunk.
    return {"count": len(vectors), "dimensions": len(vectors[0]) if vectors else 0}


# wrap_openai doesn't trace embeddings.create, so trace the call here.
@traceable(name="embed_texts", run_type="embedding", process_outputs=_summarize_vectors)
def embed_texts(texts: list[str], cfg: RuntimeConfig | None = None) -> list[list[float]]:
    """Embed texts in batches of 100, returning vectors in input order.

    cfg defaults to the runtime config; pass one to try unsaved values (admin "Test connection").
    """
    cfg = cfg or get_runtime_config()
    vectors: list[list[float]] = []
    for batch in batched(texts, BATCH_SIZE):
        response = get_client(cfg.embedding_base_url, cfg.embedding_api_key).embeddings.create(
            model=cfg.embedding_model,
            input=list(batch),
            dimensions=cfg.embedding_dimensions,
        )
        for item in sorted(response.data, key=lambda d: d.index):
            assert len(item.embedding) == cfg.embedding_dimensions, "unexpected embedding size"
            vectors.append(item.embedding)
    return vectors


def embed_query(text: str, cfg: RuntimeConfig | None = None) -> list[float]:
    """Embed one search query with the same model and dimensions as the stored chunks (sync)."""
    return embed_texts([text], cfg)[0]
