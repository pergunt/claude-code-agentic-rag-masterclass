"""LangSmith trace checks for OBS-01 / OBS-02.

    python -m app.scripts.check_traces --since <iso> --user-id <val-a id> [--out traces.json]

Writes [{"id", "status": PASS|FAIL|SKIP, "message"}]. Prints only booleans about config.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import app.config  # noqa: F401  (loads .env into os.environ)

POLL_SECONDS = 90
POLL_INTERVAL = 5


def _meta(run) -> dict:
    return ((run.extra or {}).get("metadata")) or {}


def _list_runs(client, **kwargs):
    fn = getattr(client, "list_runs")
    return list(fn(**kwargs))


def check_obs01(client, project, since, user_id) -> tuple[bool, str]:
    roots = [
        r
        for r in _list_runs(client, project_name=project, is_root=True, start_time=since,
                            filter='eq(name, "chat_turn")')
        if _meta(r).get("user_id") == user_id
    ]
    if not roots:
        return False, f"no chat_turn root run since {since.isoformat()} for user {user_id}"
    best = "no complete trace"
    for root in sorted(roots, key=lambda r: r.start_time, reverse=True):
        meta = _meta(root)
        missing_meta = [k for k in ("thread_id", "user_id", "model") if not meta.get(k)]
        runs = _list_runs(client, project_name=project, trace_id=root.trace_id)
        llm = [r for r in runs if r.run_type == "llm"]
        search = [r for r in runs if r.name == "search_documents" and r.run_type == "tool"]
        embed_ids = {r.parent_run_id for r in runs if r.name == "embed_texts" and r.run_type == "embedding"}
        match_ids = {r.parent_run_id for r in runs if r.name == "match_chunks" and r.run_type == "retriever"}
        problems = []
        if missing_meta:
            problems.append(f"metadata missing {missing_meta}")
        if len(llm) < 2:
            problems.append(f"{len(llm)} llm runs (need >= 2)")
        if not search:
            problems.append("no search_documents tool run")
        else:
            ids = {s.id for s in search}
            # embed/match may be nested deeper; accept direct children or any descendant via parent chain
            by_id = {r.id: r for r in runs}

            def under_search(pid):
                while pid:
                    if pid in ids:
                        return True
                    parent = by_id.get(pid)
                    pid = parent.parent_run_id if parent else None
                return False

            if not any(under_search(i) for i in embed_ids):
                problems.append("no embed_texts [embedding] under search_documents")
            if not any(under_search(i) for i in match_ids):
                problems.append("no match_chunks [retriever] under search_documents")
        if not problems:
            return True, f"chat_turn {root.id}: {len(llm)} llm runs, search_documents > embed_texts + match_chunks"
        best = f"chat_turn {root.id}: " + "; ".join(problems)
    return False, best


def check_obs02(client, project, since) -> tuple[bool, str]:
    roots = _list_runs(client, project_name=project, start_time=since,
                       filter='eq(name, "ingest_document")')
    if not roots:
        return False, f"no ingest_document run since {since.isoformat()}"
    best = ""
    for root in roots:
        meta = _meta(root)
        problems = [f"metadata missing {k}" for k in ("document_id", "chunk_count") if meta.get(k) is None]
        runs = _list_runs(client, project_name=project, trace_id=root.trace_id)
        if not any(r.name == "embed_texts" for r in runs):
            problems.append("no embed_texts child")
        if not problems:
            return True, f"ingest_document {root.id}: document_id, chunk_count={meta.get('chunk_count')}, embed_texts child"
        best = f"ingest_document {root.id}: " + "; ".join(problems)
    return False, best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--user-id", default="")
    ap.add_argument("--out", default="traces.json")
    args = ap.parse_args()

    tracing = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    has_key = bool(os.environ.get("LANGSMITH_API_KEY"))
    print(f"tracing_enabled={tracing} api_key_set={has_key}")
    ids = ("OBS-01", "OBS-02")
    if not (tracing and has_key):
        results = [{"id": i, "status": "SKIP", "message": "LangSmith tracing disabled or no API key"} for i in ids]
    else:
        from langsmith import Client

        client = Client()
        project = os.environ.get("LANGSMITH_PROJECT", "agentic-rag-masterclass")
        since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        done: dict[str, tuple[bool, str]] = {}
        checks = {
            "OBS-01": lambda: check_obs01(client, project, since, args.user_id),
            "OBS-02": lambda: check_obs02(client, project, since),
        }
        deadline = time.time() + POLL_SECONDS
        while True:
            for i, fn in checks.items():
                if i in done and done[i][0]:
                    continue
                try:
                    done[i] = fn()
                except Exception as exc:  # noqa: BLE001
                    done[i] = (False, f"LangSmith query error: {type(exc).__name__}: {exc}"[:300])
            if all(done[i][0] for i in ids) or time.time() >= deadline:
                break
            time.sleep(POLL_INTERVAL)
        results = [{"id": i, "status": "PASS" if done[i][0] else "FAIL", "message": done[i][1]} for i in ids]
    Path(args.out).write_text(json.dumps(results, indent=2))
    for r in results:
        print(f"{r['id']}: {r['status']} - {r['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
