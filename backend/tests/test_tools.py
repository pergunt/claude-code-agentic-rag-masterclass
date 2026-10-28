import pytest

from app.services import tools
from app.services.retrieval import ChunkHit
from app.services.tools import TOOL_SCHEMAS, ToolContext, execute_tool

CTX = ToolContext(db=None, user_id="u1")  # search_chunks is monkeypatched, db is unused


def hit(filename: str, chunk_index: int, similarity: float) -> ChunkHit:
    return ChunkHit(
        id=f"{filename}-{chunk_index}",
        document_id=f"doc-{filename}",
        filename=filename,
        chunk_index=chunk_index,
        content="some content",
        similarity=similarity,
    )


def test_schema_requires_query_without_titles():
    params = TOOL_SCHEMAS[0]["function"]["parameters"]
    assert params["required"] == ["query"]
    assert "title" not in params and "title" not in params["properties"]["query"]


@pytest.mark.anyio
async def test_invalid_arguments_do_not_raise():
    result = await execute_tool("search_documents", '{"q":1}', CTX)
    assert result.content.startswith("Invalid arguments")
    assert result.error


@pytest.mark.anyio
async def test_malformed_json_does_not_raise():
    result = await execute_tool("search_documents", '{"query": ', CTX)
    assert result.content.startswith("Invalid arguments")


@pytest.mark.anyio
async def test_unknown_tool():
    result = await execute_tool("nope", "{}", CTX)
    assert result.content.startswith("Unknown tool")


@pytest.mark.anyio
async def test_results_are_formatted_with_sources(monkeypatch):
    async def fake_search(db, query, *, top_k, min_similarity):
        return [hit("a.md", 3, 0.62), hit("b.md", 0, 0.41)]

    monkeypatch.setattr(tools, "search_chunks", fake_search)
    result = await execute_tool("search_documents", '{"query": "backup call sign"}', CTX)
    assert "[1] a.md, chunk 3 (similarity 0.62)" in result.content
    assert "[2] b.md, chunk 0" in result.content
    assert [s["filename"] for s in result.sources] == ["a.md", "b.md"]


@pytest.mark.anyio
async def test_empty_results(monkeypatch):
    async def fake_search(db, query, *, top_k, min_similarity):
        return []

    monkeypatch.setattr(tools, "search_chunks", fake_search)
    result = await execute_tool("search_documents", '{"query": "parking policy"}', CTX)
    assert "don't appear to cover" in result.content
    assert result.sources == []
    assert not result.error


@pytest.mark.anyio
async def test_search_failure_is_returned_as_error(monkeypatch):
    async def fake_search(db, query, *, top_k, min_similarity):
        raise RuntimeError("embedding API down")

    monkeypatch.setattr(tools, "search_chunks", fake_search)
    result = await execute_tool("search_documents", '{"query": "anything"}', CTX)
    assert result.content.startswith("Search failed")
    assert result.error
