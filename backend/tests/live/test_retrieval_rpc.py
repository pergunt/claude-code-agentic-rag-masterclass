import anyio
import httpx

from app.db import create_anon_client, create_user_client
from app.services.embeddings import embed_query
from app.services.retrieval import search_chunks


def _doc_ids(client: httpx.Client) -> set[str]:
    return {d["id"] for d in client.get("/api/documents").json()}


def test_RET_01_match_chunks_rls(env, a, b):
    ids_a, ids_b = _doc_ids(a), _doc_ids(b)
    assert env["a"]["doc_id"] in ids_a and env["b"]["doc_id"] in ids_b
    assert not ids_a & ids_b

    async def search(token: str):
        return await search_chunks(create_user_client(token), "recipe station", top_k=10, min_similarity=-1)

    hits_a = anyio.run(search, env["a"]["token"])
    hits_b = anyio.run(search, env["b"]["token"])
    assert hits_a and hits_b
    assert {h.document_id for h in hits_a} <= ids_a
    assert {h.document_id for h in hits_b} <= ids_b

    embedding = embed_query("recipe station")
    try:
        create_anon_client().rpc(
            "match_chunks", {"query_embedding": embedding, "match_count": 3, "match_threshold": -1}
        ).execute()
    except Exception as exc:
        assert "42501" in str(exc) or getattr(exc, "code", None) == "42501", exc
    else:
        raise AssertionError("anon match_chunks RPC should be rejected")
