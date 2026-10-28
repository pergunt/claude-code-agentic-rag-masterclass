from functools import lru_cache
from itertools import batched

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.config import get_settings

BATCH_SIZE = 100


@lru_cache
def get_client() -> OpenAI:
    # Separate from llm.py on purpose: chat may point at OpenRouter, embeddings always use OpenAI.
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return wrap_openai(OpenAI(api_key=settings.openai_api_key))


def _summarize_vectors(vectors: list[list[float]]) -> dict:
    # Keep traces small: record the shape, not 1536 floats per chunk.
    return {"count": len(vectors), "dimensions": len(vectors[0]) if vectors else 0}


# wrap_openai doesn't trace embeddings.create, so trace the call here.
@traceable(name="embed_texts", run_type="embedding", process_outputs=_summarize_vectors)
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts in batches of 100, returning vectors in input order."""
    settings = get_settings()
    vectors: list[list[float]] = []
    for batch in batched(texts, BATCH_SIZE):
        response = get_client().embeddings.create(
            model=settings.embedding_model,
            input=list(batch),
            dimensions=settings.embedding_dimensions,
        )
        for item in sorted(response.data, key=lambda d: d.index):
            assert len(item.embedding) == settings.embedding_dimensions, "unexpected embedding size"
            vectors.append(item.embedding)
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed one search query with the same model and dimensions as the stored chunks (sync)."""
    return embed_texts([text])[0]
