"""Live chat tests (CHAT-01..03): streaming, memory, disconnect."""

import time

import pytest

from .helpers import retry_llm, stream_chat

pytestmark = pytest.mark.llm


def _messages(client, thread_id):
    res = client.get(f"/api/threads/{thread_id}/messages")
    res.raise_for_status()
    return res.json()


def test_CHAT_01_streams_deltas_then_done_and_persists(a, new_thread, record_property):
    prompt = "Count from one to ten in words, separated by commas."

    def attempt(_):
        tid = new_thread(a)
        events = stream_chat(a, tid, prompt)
        types = [e["type"] for e in events]
        assert "error" not in types, events
        deltas = [e["delta"] for e in events if e["type"] == "delta"]
        dones = [e for e in events if e["type"] == "done"]
        assert len(deltas) >= 2, types
        assert len(dones) == 1
        assert events[-1]["type"] == "done"
        assert dones[0]["text"] == "".join(deltas)
        rows = _messages(a, tid)
        user = [r for r in rows if r["role"] == "user"]
        asst = [r for r in rows if r["role"] == "assistant"]
        assert len(user) == 1 and user[0]["content"] == prompt
        assert len(asst) == 1 and asst[0]["content"] == dones[0]["text"]

    retry_llm(attempt, record_property=record_property)


def test_CHAT_02_memory_across_turns(a, new_thread, record_property):
    def attempt(_):
        tid = new_thread(a)
        first = stream_chat(a, tid, "My favourite city is Lisbon. Reply briefly.")
        assert first[-1]["type"] == "done", first
        second = stream_chat(a, tid, "Which city did I mention?")
        assert second[-1]["type"] == "done", second
        assert "lisbon" in second[-1]["text"].lower()

    retry_llm(attempt, record_property=record_property)


def test_CHAT_03_disconnect_saves_partial(a, new_thread, record_property):
    def attempt(_):
        tid = new_thread(a)
        events = stream_chat(
            a,
            tid,
            "Write a detailed 800-word story about a lighthouse keeper.",
            stop_after=lambda ev: sum(e["type"] == "delta" for e in ev) >= 3,
        )
        assert sum(e["type"] == "delta" for e in events) >= 3
        deadline = time.monotonic() + 5
        saved = False
        while time.monotonic() < deadline:
            rows = _messages(a, tid)
            if any(r["role"] == "assistant" and (r["content"] or "").strip() for r in rows):
                saved = True
                break
            time.sleep(0.5)
        assert saved, "no partial assistant row within 5 s"
        follow = stream_chat(a, tid, "Thanks. Reply with one word.")
        assert follow[-1]["type"] == "done", follow

    retry_llm(attempt, record_property=record_property)
