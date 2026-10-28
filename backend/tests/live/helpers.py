"""Shared helpers for live tests: SSE chat streaming, LLM retry, Supabase REST/Storage client."""

import json
from collections.abc import Callable

import httpx


def stream_chat(
    client: httpx.Client,
    thread_id: str,
    content: str,
    stop_after: Callable[[list[dict]], bool] | None = None,
) -> list[dict]:
    """POST a chat message and return the parsed SSE events (the `data: ` JSON payloads).

    `stop_after(events)` is called after every event; when it returns True the response is
    closed early (simulates the browser disconnecting) and the events so far are returned.
    """
    events: list[dict] = []
    with client.stream("POST", f"/api/threads/{thread_id}/messages", json={"content": content}) as res:
        res.raise_for_status()
        for line in res.iter_lines():
            if not line.startswith("data: "):
                continue
            events.append(json.loads(line[len("data: "):]))
            if stop_after is not None and stop_after(events):
                break  # leaving the `with` closes the response
    return events


def retry_llm(fn: Callable[[int], None], attempts: int = 2, record_property=None) -> None:
    """Run fn(attempt) (1-based) and retry on AssertionError; callers use a fresh thread per attempt.

    A pass on a retry is recorded with record_property("flaky", retries) so the report shows
    PASS (flaky). The last AssertionError is re-raised if every attempt fails.
    """
    last: AssertionError | None = None
    for attempt in range(1, attempts + 1):
        try:
            fn(attempt)
        except AssertionError as exc:
            last = exc
            continue
        if attempt > 1 and record_property is not None:
            record_property("flaky", attempt - 1)
        return
    assert last is not None
    raise last


def rest(env: dict, token: str) -> httpx.Client:
    """Client for Supabase PostgREST (/rest/v1/...) and Storage (/storage/v1/...) as the user."""
    return httpx.Client(
        base_url=env["supabase_url"],
        headers={"apikey": env["anon_key"], "Authorization": f"Bearer {token}"},
        timeout=60,
    )
