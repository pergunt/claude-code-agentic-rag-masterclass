import json
from types import SimpleNamespace as NS

import pytest

from app.services import llm, tools
from app.services.retrieval import ChunkHit
from app.services.tools import ToolContext


def tool_call_chunk(call_id: str, query: str) -> NS:
    fn = NS(name="search_documents", arguments=json.dumps({"query": query}))
    delta = NS(content=None, tool_calls=[NS(index=0, id=call_id, function=fn)])
    return NS(choices=[NS(delta=delta, finish_reason=None)])


def text_chunk(text: str, finish_reason: str | None = None) -> NS:
    return NS(choices=[NS(delta=NS(content=text, tool_calls=None), finish_reason=finish_reason)])


USAGE_CHUNK = NS(choices=[])


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for chunk in self.chunks:
            yield chunk


class FakeClient:
    """chat.completions.create returns the next scripted stream; the last script repeats."""

    def __init__(self, scripts):
        self.scripts = scripts
        self.calls: list[dict] = []
        self.chat = NS(completions=NS(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        script = self.scripts[min(len(self.calls) - 1, len(self.scripts) - 1)]
        return FakeStream(script)


@pytest.fixture
def fake_search(monkeypatch):
    searches: list[str] = []

    async def search(db, query, *, top_k, min_similarity):
        searches.append(query)
        return [
            ChunkHit(
                id="c1", document_id="d1", filename="a.md", chunk_index=2, content="Grey Reed", similarity=0.7
            )
        ]

    monkeypatch.setattr(tools, "search_chunks", search)
    return searches


def use_client(monkeypatch, client: FakeClient) -> None:
    monkeypatch.setattr(llm, "get_chat_client", lambda: client)


CTX = ToolContext(db=None, user_id="u1")
HISTORY = [{"role": "user", "content": "What is the backup call sign?"}]


async def collect(ctx=CTX):
    return [e async for e in llm.stream_reply(HISTORY, ctx)]


def test_RET_07_cited_sources_keeps_only_mentioned_files_deduped():
    def src(filename, chunk, sim):
        return {"document_id": filename, "filename": filename, "chunk_index": chunk, "similarity": sim}

    retrieved = [src("a.md", 1, 0.4), src("b.md", 0, 0.2), src("a.md", 1, 0.5), src("a.md", 3, 0.3)]
    cited = llm.cited_sources(retrieved, "Answer (a.md, chunk 1).")
    assert [(s["chunk_index"], s["similarity"]) for s in cited] == [(1, 0.5), (3, 0.3)]
    assert llm.cited_sources(retrieved, "Your documents don't cover this.") == []


@pytest.mark.anyio
async def test_RET_07_tool_round_then_answer(monkeypatch, fake_search):
    client = FakeClient(
        [
            [tool_call_chunk("c1", "backup call sign"), text_chunk("", "tool_calls"), USAGE_CHUNK],
            [text_chunk("It is "), text_chunk("Grey Reed (a.md, chunk 2).", "stop"), USAGE_CHUNK],
        ]
    )
    use_client(monkeypatch, client)
    events = await collect()

    assert [(e["type"], e.get("status")) for e in events] == [
        ("tool", "searching"),
        ("tool", "completed"),
        ("delta", None),
        ("delta", None),
        ("done", None),
    ]
    assert events[0]["query"] == "backup call sign"
    assert events[1]["sources"][0]["filename"] == "a.md"
    done = events[-1]
    assert done["text"] == "It is Grey Reed (a.md, chunk 2)."
    assert [s["chunk_index"] for s in done["sources"]] == [2]
    # Round 2 saw the assistant tool_calls message followed by the matching tool result.
    roles = [m["role"] for m in client.calls[1]["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert client.calls[1]["messages"][3]["tool_call_id"] == "c1"


@pytest.mark.anyio
async def test_RET_07_tool_loop_is_bounded(monkeypatch, fake_search):
    always_tool = [tool_call_chunk("c", "again"), text_chunk("", "tool_calls")]
    client = FakeClient([always_tool])
    use_client(monkeypatch, client)
    max_rounds = llm.get_settings().agent_max_tool_rounds
    events = await collect()

    assert len(fake_search) == max_rounds  # exactly max_rounds tool executions
    assert len(client.calls) == max_rounds + 1
    assert client.calls[-1]["tool_choice"] == "none"
    assert client.calls[-1]["tools"]  # still declared on the last call
    assert events[-1]["type"] == "done"
    assert "couldn't complete the search" in events[-1]["text"]


@pytest.mark.anyio
async def test_RET_07_no_context_sends_no_tools(monkeypatch):
    client = FakeClient([[text_chunk("Hello", "stop")]])
    use_client(monkeypatch, client)
    events = await collect(ctx=None)

    assert events[-1] == {"type": "done", "text": "Hello", "sources": []}
    assert client.calls[0]["tools"] is llm.openai.omit
    assert client.calls[0]["messages"][0]["role"] == "system"
