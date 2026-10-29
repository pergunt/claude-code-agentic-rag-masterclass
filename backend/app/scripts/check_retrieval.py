"""Check match_chunks per user: cross-user isolation (RLS) and similarity calibration.

Usage: venv/bin/python -m app.scripts.check_retrieval "query" --as rag-test-a@example.com \
           [--as rag-test-b@example.com] [--threshold -1] [--top-k 10]
Prints `similarity  filename#chunk_index  first 80 chars` per user, then one RPC call with no JWT.
"""

import argparse

import anyio

from app.config import get_settings
from app.db import create_anon_client, create_user_client
from app.scripts.dev_tokens import sign_in
from app.services.app_settings import get_runtime_config
from app.services.embeddings import embed_query
from app.services.retrieval import search_chunks


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--as", dest="emails", action="append", required=True, metavar="EMAIL")
    parser.add_argument("--threshold", type=float, default=get_settings().retrieval_min_similarity)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    print(f"embedding model: {get_runtime_config().embedding_model}")
    print(f"query: {args.query!r}  threshold: {args.threshold}  top_k: {args.top_k}")
    for email in args.emails:
        token, _ = sign_in(email)
        hits = await search_chunks(
            create_user_client(token), args.query, top_k=args.top_k, min_similarity=args.threshold
        )
        print(f"\n== {email}: {len(hits)} hits")
        for hit in hits:
            snippet = hit.content[:80].replace("\n", " ")
            print(f"{hit.similarity:.3f}  {hit.filename}#{hit.chunk_index}  {snippet}")

    # No JWT: the RPC is revoked from anon, so this should fail with a permission error.
    embedding = embed_query(args.query)
    try:
        create_anon_client().rpc(
            "match_chunks", {"query_embedding": embedding, "match_count": 3, "match_threshold": -1}
        ).execute()
        print("\n== anon: UNEXPECTED success (match_chunks should not be callable without a JWT)")
    except Exception as exc:
        print(f"\n== anon: rejected as expected: {exc}")


if __name__ == "__main__":
    anyio.run(main)
