"""Live retrieval-in-chat tests (RET-02..06)."""

import pytest

from .helpers import retry_llm, stream_chat

pytestmark = pytest.mark.llm

QUESTION = "How long can samples wait before the cold room?"
VELMORA = "velmora-station.md"


def _messages(client, thread_id):
    res = client.get(f"/api/threads/{thread_id}/messages")
    res.raise_for_status()
    return res.json()


def _tool_events(events, status):
    return [e for e in events if e["type"] == "tool" and e["status"] == status]


def test_RET_02_grounded_answer_cites_velmora(a, new_thread, record_property):
    def attempt(_):
        tid = new_thread(a)
        events = stream_chat(a, tid, QUESTION)
        types = [e["type"] for e in events]
        assert "error" not in types, events
        searching = _tool_events(events, "searching")
        assert searching and all(e["query"].strip() for e in searching)
        completed = _tool_events(events, "completed")
        assert completed
        srcs = [s for e in completed for s in e["sources"]]
        assert len(srcs) >= 1 and all(s["filename"] == VELMORA for s in srcs), srcs
        assert types.index("tool") < types.index("delta")
        assert events[-1]["type"] == "done"
        done = events[-1]
        assert "40" in done["text"]
        assert VELMORA in done["text"]
        assert done["sources"] and all(s["filename"] == VELMORA for s in done["sources"])
        rows = _messages(a, tid)
        assert len(rows) == 2
        asst = [r for r in rows if r["role"] == "assistant"]
        assert len(asst) == 1 and asst[0]["sources"]

    retry_llm(attempt, record_property=record_property)


def test_RET_03_not_covered_has_no_sources(a, new_thread, record_property):
    def attempt(_):
        tid = new_thread(a)
        events = stream_chat(a, tid, "What does my document say about the parking policy?")
        assert events[-1]["type"] == "done", events
        done = events[-1]
        assert done["sources"] == []
        assert "chunk" not in done["text"].lower()
        asst = [r for r in _messages(a, tid) if r["role"] == "assistant"]
        assert len(asst) == 1 and asst[0]["sources"] is None

    retry_llm(attempt, record_property=record_property)


def test_RET_04_small_talk_does_not_search(a, new_thread, record_property):
    def attempt(_):
        tid = new_thread(a)
        events = stream_chat(a, tid, "hi")
        assert events[-1]["type"] == "done", events
        assert not [e for e in events if e["type"] == "tool"]

    retry_llm(attempt, record_property=record_property)


def test_RET_05_cross_user_isolation(env, b, new_thread, record_property):
    def attempt(_):
        tid = new_thread(b)
        events = stream_chat(b, tid, QUESTION)
        assert "error" not in [e["type"] for e in events], events
        for e in events:
            if e["type"] in ("tool", "done"):
                for s in e.get("sources") or []:
                    assert s.get("filename") != VELMORA, s
                    assert s.get("document_id") != env["a"]["doc_id"], s

    retry_llm(attempt, record_property=record_property)


def test_RET_06_disconnect_during_search(a, new_thread, record_property):
    def attempt(_):
        tid = new_thread(a)
        events = stream_chat(
            a,
            tid,
            QUESTION,
            stop_after=lambda ev: any(e["type"] == "tool" and e["status"] == "searching" for e in ev),
        )
        assert _tool_events(events, "searching"), events
        follow = stream_chat(a, tid, "What is the elevation of the station?")
        assert "error" not in [e["type"] for e in follow], follow
        assert follow[-1]["type"] == "done", follow

    retry_llm(attempt, record_property=record_property)
