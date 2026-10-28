import anyio.to_thread
from langsmith import traceable
from pydantic import BaseModel
from supabase import Client

from app.services.embeddings import embed_query


class ChunkHit(BaseModel):
    id: str
    document_id: str
    filename: str
    chunk_index: int
    content: str
    similarity: float


def _as_retriever_output(hits: list[ChunkHit]) -> dict:
    # LangSmith's retriever run shape, so the UI renders the passages as documents.
    return {
        "documents": [
            {
                "page_content": h.content,
                "type": "Document",
                "metadata": {
                    "filename": h.filename,
                    "chunk_index": h.chunk_index,
                    "similarity": h.similarity,
                },
            }
            for h in hits
        ]
    }


@traceable(run_type="retriever", name="match_chunks", process_outputs=_as_retriever_output)
def _rpc(db: Client, embedding: list[float], top_k: int, min_similarity: float) -> list[ChunkHit]:
    # If PostgREST rejects the list for the vector param, pass str(embedding) instead.
    rows = (
        db.rpc(
            "match_chunks",
            {
                "query_embedding": embedding,
                "match_count": top_k,
                "match_threshold": min_similarity,
            },
        )
        .execute()
        .data
    )
    return [ChunkHit(**row) for row in rows]


def _embed_and_match(db: Client, query: str, top_k: int, min_similarity: float) -> list[ChunkHit]:
    return _rpc(db, embed_query(query), top_k, min_similarity)


async def search_chunks(
    db: Client, query: str, *, top_k: int, min_similarity: float
) -> list[ChunkHit]:
    """Vector search over the caller's own chunks (RLS via the user's JWT), most similar first.

    The embedding call and the Supabase client are both sync, so they share one worker thread.
    This is the seam for metadata filters (Module 4) and hybrid search + rerank (Module 6).
    """
    return await anyio.to_thread.run_sync(_embed_and_match, db, query, top_k, min_similarity)
