import json
import time
import uuid

import httpx
import pytest

from app.config import get_settings
from app.services.ingestion import BUCKET
from tests.live.helpers import rest

MD = "# Title\n\n" + "\n\n".join(f"Paragraph {i}: " + ("lorem ipsum dolor sit amet " * 20) for i in range(12))


def upload(client, name: str, data: bytes, mime: str = "text/markdown"):
    return client.post("/api/documents", files={"file": (name, data, mime)})


def wait_done(client, doc_id: str, timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        doc = client.get(f"/api/documents/{doc_id}").json()
        if doc["status"] in ("completed", "failed"):
            return doc
        time.sleep(1)
    raise AssertionError(f"document {doc_id} not finished in {timeout}s")


def storage_path(env, user: str, doc_id: str) -> str:
    with rest(env, env[user]["token"]) as r:
        rows = r.get("/rest/v1/documents", params={"select": "storage_path", "id": f"eq.{doc_id}"}).json()
    return rows[0]["storage_path"]


@pytest.fixture
def uploaded(a):
    """Factory: upload as A, wait for completion; deletes at teardown."""
    ids: list[str] = []

    def make(name: str, data: bytes) -> dict:
        res = upload(a, name, data)
        assert res.status_code == 201, res.text
        ids.append(res.json()["id"])
        return res.json()

    yield make
    for i in ids:
        a.delete(f"/api/documents/{i}")


def test_ING_01_pipeline(env, a, uploaded):
    data = MD.encode()
    created = uploaded(f"ing01-{uuid.uuid4().hex[:6]}.md", data)
    assert created["status"] == "pending"
    doc = wait_done(a, created["id"])
    assert doc["status"] == "completed" and doc["error"] is None
    with rest(env, env["a"]["token"]) as r:
        res = r.get(
            "/rest/v1/chunks",
            params={
                "document_id": f"eq.{doc['id']}",
                "select": "chunk_index,content,embedding",
                "order": "chunk_index",
            },
        )
    chunks = res.json()
    assert doc["chunk_count"] == len(chunks) > 0
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
    size = get_settings().chunk_size
    for c in chunks:
        assert len(c["content"]) <= size
        emb = c["embedding"]
        if isinstance(emb, str):
            emb = json.loads(emb)
        assert len(emb) == 1536


def test_ING_02_storage_roundtrip(env, a, uploaded):
    data = ("Storage roundtrip content. " * 30).encode()
    created = uploaded(f"ing02-{uuid.uuid4().hex[:6]}.txt", data)
    wait_done(a, created["id"])
    path = storage_path(env, "a", created["id"])
    with rest(env, env["a"]["token"]) as r:
        res = r.get(f"/storage/v1/object/{BUCKET}/{path}")
    assert res.status_code == 200
    assert res.content == data


def test_ING_03_upload_rejections(env, a):
    assert upload(a, "x.pdf", b"%PDF-1.4", "application/pdf").status_code == 415
    assert upload(a, "empty.txt", b"", "text/plain").status_code == 400
    too_big = b"a" * (get_settings().max_upload_bytes + 1)
    assert upload(a, "big.txt", too_big, "text/plain").status_code == 413
    assert upload(a, "bad.txt", b"\xff\xfe\x00bad", "text/plain").status_code == 415
    res = httpx.post(
        f"{env['api']}/api/documents", files={"file": ("n.txt", b"hello", "text/plain")}, timeout=30
    )
    assert res.status_code == 401


def test_ING_04_cross_user_isolation(env, a, b, uploaded):
    created = uploaded(f"ing04-{uuid.uuid4().hex[:6]}.txt", b"Isolation test content for user A only.")
    doc_id = created["id"]
    wait_done(a, doc_id)
    path = storage_path(env, "a", doc_id)

    assert b.get(f"/api/documents/{doc_id}").status_code == 404
    assert b.delete(f"/api/documents/{doc_id}").status_code == 404
    assert a.get(f"/api/documents/{doc_id}").status_code == 200

    with rest(env, env["b"]["token"]) as r:
        assert r.get("/rest/v1/documents", params={"select": "id", "id": f"eq.{doc_id}"}).json() == []
        assert r.get("/rest/v1/chunks", params={"select": "id", "document_id": f"eq.{doc_id}"}).json() == []
        assert r.get(f"/storage/v1/object/{BUCKET}/{path}").status_code in (400, 404)
        evil = r.post(
            f"/storage/v1/object/{BUCKET}/{env['a']['id']}/evil-{uuid.uuid4().hex[:6]}.txt",
            content=b"x",
            headers={"Content-Type": "text/plain"},
        )
        assert evil.status_code in (400, 403), evil.text


def test_ING_05_least_privilege(env, a, uploaded):
    created = uploaded(f"ing05-{uuid.uuid4().hex[:6]}.txt", b"Least privilege content, long enough to chunk.")
    doc_id = created["id"]
    doc = wait_done(a, doc_id)
    assert doc["status"] == "completed"
    with rest(env, env["a"]["token"]) as r:
        ins = r.post(
            "/rest/v1/chunks",
            json={
                "document_id": doc_id,
                "user_id": env["a"]["id"],
                "chunk_index": 99,
                "content": "forged",
                "embedding": [0.0] * 1536,
            },
        )
        assert ins.status_code >= 400, ins.text
        patch = r.patch(
            "/rest/v1/documents",
            params={"id": f"eq.{doc_id}"},
            json={"status": "failed"},
            headers={"Prefer": "return=representation"},
        )
        assert patch.status_code < 300 and patch.json() == [], (patch.status_code, patch.text)
    assert a.get(f"/api/documents/{doc_id}").json()["status"] == "completed"


def test_ING_08_delete(env, a):
    phrase = f"Zorvath crystal resonance protocol {uuid.uuid4().hex[:8]} governs the lantern harmonics."
    res = upload(a, f"ing08-{uuid.uuid4().hex[:6]}.txt", phrase.encode(), "text/plain")
    assert res.status_code == 201, res.text
    doc_id = res.json()["id"]
    try:
        assert wait_done(a, doc_id)["status"] == "completed"
        path = storage_path(env, "a", doc_id)

        import anyio

        from app.db import create_user_client
        from app.services.retrieval import search_chunks

        async def search():
            return await search_chunks(create_user_client(env["a"]["token"]), phrase, top_k=10, min_similarity=-1)

        assert doc_id in {h.document_id for h in anyio.run(search)}
    except BaseException:
        a.delete(f"/api/documents/{doc_id}")
        raise

    assert a.delete(f"/api/documents/{doc_id}").status_code == 204
    assert a.get(f"/api/documents/{doc_id}").status_code == 404
    with rest(env, env["a"]["token"]) as r:
        assert r.get("/rest/v1/chunks", params={"select": "id", "document_id": f"eq.{doc_id}"}).json() == []
        assert r.get(f"/storage/v1/object/{BUCKET}/{path}").status_code in (400, 404)
    assert doc_id not in {h.document_id for h in anyio.run(search)}
