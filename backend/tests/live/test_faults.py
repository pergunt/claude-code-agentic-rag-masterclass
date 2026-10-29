"""In-process fault injection (ASGI transport, no network to the backend)."""

import asyncio
import json
import uuid

import httpx
import pytest

import app.main
import app.services.ingestion as ingestion
import app.services.llm as llm
from tests.live.helpers import rest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def asgi(env: dict) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.main.app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {env['a']['token']}"},
        timeout=60,
    )


@pytest.mark.anyio
async def test_CHAT_04_provider_error(env, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("injected LLM failure")

    monkeypatch.setattr(llm, "get_chat_client", boom)
    async with asgi(env) as c:
        tid = (await c.post("/api/threads", json={})).json()["id"]
        try:
            res = await c.post(f"/api/threads/{tid}/messages", json={"content": "hello there"})
            assert res.status_code == 200
            events = [json.loads(l[6:]) for l in res.text.splitlines() if l.startswith("data: ")]
            types = [e["type"] for e in events]
            assert "error" in types and "done" not in types
            assert any("injected LLM failure" in e.get("message", "") for e in events)
            msgs = (await c.get(f"/api/threads/{tid}/messages")).json()
            assert [m["role"] for m in msgs] == ["user"]
            assert msgs[0]["content"] == "hello there"
        finally:
            await c.delete(f"/api/threads/{tid}")


@pytest.mark.anyio
async def test_ING_06_embedding_failure(env, monkeypatch):
    def boom(texts, cfg=None):
        raise RuntimeError("injected embedding failure")

    monkeypatch.setattr(ingestion, "embed_texts", boom)
    async with asgi(env) as c:
        res = await c.post(
            "/api/documents",
            files={"file": (f"ing06-{uuid.uuid4().hex[:6]}.md", b"# Fault\n\nSome text to embed.", "text/markdown")},
        )
        assert res.status_code == 201, res.text
        doc_id = res.json()["id"]
        try:
            doc = None
            for _ in range(60):
                doc = (await c.get(f"/api/documents/{doc_id}")).json()
                if doc["status"] in ("completed", "failed"):
                    break
                await asyncio.sleep(1)
            assert doc["status"] == "failed", doc
            assert "injected embedding failure" in doc["error"]
            assert doc["chunk_count"] == 0
            with rest(env, env["a"]["token"]) as r:
                chunks = r.get("/rest/v1/chunks", params={"select": "id", "document_id": f"eq.{doc_id}"})
            assert chunks.json() == []
        finally:
            await c.delete(f"/api/documents/{doc_id}")
