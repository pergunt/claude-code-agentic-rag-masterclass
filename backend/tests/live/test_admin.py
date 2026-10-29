"""Admin role (ADM-01, ADM-02) and runtime settings API (ADM-03..ADM-08)."""

import contextlib

import pytest

from .helpers import retry_llm, rest, stream_chat

FIELDS = ("llm_base_url", "llm_model", "llm_api_key", "embedding_base_url", "embedding_model", "embedding_api_key")
TEXT_FIELDS = ("llm_base_url", "llm_model", "embedding_base_url", "embedding_model")
DUMMY_KEY = "dummy-key-1234567890"
ADMIN_ROUTES = (
    ("get", "/api/admin/settings", None),
    ("put", "/api/admin/settings", {"llm_model": "x/y"}),
    ("post", "/api/admin/settings/test", {}),
)


@contextlib.contextmanager
def settings_reset(admin):
    """Yield, then always reset all six overridable fields to the env defaults."""
    try:
        yield
    finally:
        res = admin.put("/api/admin/settings", json={name: None for name in FIELDS})
        assert res.status_code == 200, res.text


def _settings(admin) -> dict:
    res = admin.get("/api/admin/settings")
    assert res.status_code == 200, res.text
    return res.json()


def test_ADM_01_profiles_rls(env, a, anon_rest):
    own_id = env["a"]["id"]
    with rest(env, env["a"]["token"]) as r:
        rows = r.get("/rest/v1/profiles", params={"select": "id,is_admin"}).json()
        assert [row["id"] for row in rows] == [own_id]
        assert rows[0]["is_admin"] is False

        # No write policy: a self-promotion PATCH matches no rows and changes nothing.
        res = r.patch(
            "/rest/v1/profiles",
            params={"id": f"eq.{own_id}"},
            json={"is_admin": True},
            headers={"Prefer": "return=representation"},
        )
        assert res.status_code in (200, 204, 401, 403)
        if res.status_code == 200:
            assert res.json() == []
        again = r.get("/rest/v1/profiles", params={"select": "is_admin", "id": f"eq.{own_id}"}).json()
        assert again == [{"is_admin": False}]

    anon = anon_rest.get("/rest/v1/profiles", params={"select": "id"})
    assert anon.status_code == 200 and anon.json() == []


def test_ADM_02_me_is_admin(a, admin):
    assert a.get("/api/me").json()["is_admin"] is False
    assert admin.get("/api/me").json()["is_admin"] is True


def test_ADM_03_admin_only(env, a, admin):
    for method, path, body in ADMIN_ROUTES:
        res = getattr(a, method)(path, **({"json": body} if body is not None else {}))
        assert res.status_code == 403, (method, path, res.status_code)
        assert getattr(admin, "get")("/api/admin/settings").status_code == 200

    with rest(env, env["a"]["token"]) as r:
        assert r.get("/rest/v1/app_settings", params={"select": "*"}).json() == []
        res = r.post("/rest/v1/rpc/set_app_secret", json={"p_name": "llm_api_key", "p_value": DUMMY_KEY})
        assert res.status_code >= 400
        res = r.post("/rest/v1/rpc/get_app_secrets", json={})
        assert res.status_code in (401, 403) and res.json().get("code") == "42501"
    with rest(env, env["admin"]["token"]) as r:  # not even an admin JWT can decrypt keys
        res = r.post("/rest/v1/rpc/get_app_secrets", json={})
        assert res.status_code in (401, 403) and res.json().get("code") == "42501"


def test_ADM_04_secrets_never_leave_the_server(admin):
    with settings_reset(admin):
        put = admin.put("/api/admin/settings", json={"embedding_api_key": DUMMY_KEY})
        assert put.status_code == 200, put.text
        got = admin.get("/api/admin/settings")
        for res in (put, got):
            assert DUMMY_KEY not in res.text
            key = res.json()["embedding_api_key"]
            assert key == {"configured": True, "source": "app", "last4": "7890"}
    after = _settings(admin)["embedding_api_key"]
    assert after["source"] == "env" and DUMMY_KEY not in str(after)


@pytest.mark.llm
def test_ADM_05_override_and_reset(a, admin, new_thread, record_property):
    before = _settings(admin)
    model, emb_url = before["llm_model"]["value"], before["embedding_base_url"]["value"]
    with settings_reset(admin):
        res = admin.put("/api/admin/settings", json={"llm_model": model, "embedding_base_url": emb_url})
        assert res.status_code == 200, res.text
        now = _settings(admin)
        assert now["llm_model"]["value"] == model and now["llm_model"]["source"] == "app"
        assert now["embedding_base_url"]["value"] == emb_url and now["embedding_base_url"]["source"] == "app"
        assert now["embedding_dimensions"] == 1536

        def attempt(_):
            events = stream_chat(a, new_thread(a), "How long can samples wait before the cold room?")
            assert events[-1]["type"] == "done", events
            assert "velmora-station.md" in events[-1]["text"]
            assert events[-1]["sources"]

        retry_llm(attempt, record_property=record_property)

        assert admin.put("/api/admin/settings", json={"llm_model": None, "embedding_base_url": None}).status_code == 200
        reset = _settings(admin)
        for name in ("llm_model", "embedding_base_url"):
            assert reset[name]["value"] == before[name]["value"] and reset[name]["source"] == "env"
        # embedding_dimensions is fixed server-side
        assert admin.put("/api/admin/settings", json={"embedding_dimensions": 768}).status_code == 422
        for bad in ({"llm_base_url": "http://example.com/v1"}, {"llm_model": "has space"}, {"llm_api_key": "short"}):
            assert admin.put("/api/admin/settings", json=bad).status_code == 422


@pytest.mark.llm
def test_ADM_06_bad_model_surfaces_cleanly(a, admin, new_thread, record_property):
    with settings_reset(admin):
        assert admin.put("/api/admin/settings", json={"llm_model": "nonexistent/model"}).status_code == 200
        events = stream_chat(a, new_thread(a), "Say hello")
        assert [e for e in events if e["type"] == "error"], events
        assert events[-1]["type"] == "error" and "Traceback" not in events[-1]["message"]

        assert admin.put("/api/admin/settings", json={"llm_model": None}).status_code == 200

        def attempt(_):
            events = stream_chat(a, new_thread(a), "Say hello")
            assert events[-1]["type"] == "done", events

        retry_llm(attempt, record_property=record_property)


@pytest.mark.llm
def test_ADM_07_test_connection(admin):
    with settings_reset(admin):
        before = _settings(admin)
        res = admin.post("/api/admin/settings/test", json={})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["chat"]["ok"] is True, body
        assert body["embeddings"]["ok"] is True and body["embeddings"]["dimensions"] == 1536, body

        bogus = "sk-bogus-0000000000"
        res = admin.post("/api/admin/settings/test", json={"llm_api_key": bogus})
        assert res.status_code == 200
        chat = res.json()["chat"]
        assert chat["ok"] is False and chat["error"] and bogus not in res.text
        assert _settings(admin) == before  # nothing saved


def test_ADM_08_embedding_lock(admin, env):
    with rest(env, env["a"]["token"]) as r:  # DocumentOut doesn't expose it; read the own row via REST
        rows = r.get("/rest/v1/documents", params={"select": "embedding_model", "id": f"eq.{env['a']['doc_id']}"}).json()
    assert rows and rows[0]["embedding_model"], rows  # set by process_document at seed time
    with settings_reset(admin):
        base = _settings(admin)
        assert base["embedding_locked"] is True and base["chunk_count"] > 0

        res = admin.put("/api/admin/settings", json={"embedding_model": "text-embedding-3-large"})
        assert res.status_code == 409, res.text
        assert "locked" in res.json()["detail"]
        after = _settings(admin)
        assert after["embedding_model"] == base["embedding_model"]

        res = admin.put("/api/admin/settings", json={"embedding_base_url": "https://example.com/v1"})
        assert res.status_code == 409, res.text
        assert _settings(admin)["embedding_base_url"] == base["embedding_base_url"]

        same = {name: base[name]["value"] for name in ("embedding_model", "embedding_base_url")}
        res = admin.put("/api/admin/settings", json=same)
        assert res.status_code == 200, res.text
