import time

import httpx


def test_THR_01_thread_crud(a, new_thread):
    start = time.monotonic()
    res = a.post("/api/threads", json={})
    elapsed = time.monotonic() - start
    assert res.status_code == 201
    assert elapsed < 1.5
    thread = res.json()
    tid = thread["id"]
    assert "openai_conversation_id" not in thread
    try:
        listed = a.get("/api/threads").json()
        assert tid in [t["id"] for t in listed]
        stamps = [t["updated_at"] for t in listed]
        assert stamps == sorted(stamps, reverse=True)

        patched = a.patch(f"/api/threads/{tid}", json={"title": "Renamed thread"})
        assert patched.status_code == 200
        assert patched.json()["title"] == "Renamed thread"
        assert next(t for t in a.get("/api/threads").json() if t["id"] == tid)["title"] == "Renamed thread"
    finally:
        deleted = a.delete(f"/api/threads/{tid}")
    assert deleted.status_code == 204
    assert a.get(f"/api/threads/{tid}/messages").status_code == 404
    assert a.delete(f"/api/threads/{tid}").status_code == 404


def test_THR_02_input_validation(a, new_thread):
    tid = new_thread(a)
    assert a.patch(f"/api/threads/{tid}", json={"title": ""}).status_code == 422
    assert a.patch(f"/api/threads/{tid}", json={"title": "x" * 201}).status_code == 422
    assert a.post(f"/api/threads/{tid}/messages", json={"content": ""}).status_code == 422


def test_THR_03_cross_user_isolation(a, b, new_thread):
    tid = new_thread(a)
    before_thread = next(t for t in a.get("/api/threads").json() if t["id"] == tid)
    before_msgs = a.get(f"/api/threads/{tid}/messages").json()

    assert b.get(f"/api/threads/{tid}/messages").status_code == 404
    assert b.patch(f"/api/threads/{tid}", json={"title": "hacked"}).status_code == 404
    assert b.delete(f"/api/threads/{tid}").status_code == 404
    assert b.post(f"/api/threads/{tid}/messages", json={"content": "hi"}).status_code == 404

    after_thread = next(t for t in a.get("/api/threads").json() if t["id"] == tid)
    assert after_thread == before_thread
    assert a.get(f"/api/threads/{tid}/messages").json() == before_msgs == []
    assert tid not in [t["id"] for t in b.get("/api/threads").json()]


def test_THR_04_anon_rest_blocked(anon_rest):
    for table in ("threads", "messages", "documents", "chunks"):
        res = anon_rest.get(f"/rest/v1/{table}", params={"select": "id"})
        assert res.status_code == 200, (table, res.status_code, res.text)
        assert res.json() == [], table
