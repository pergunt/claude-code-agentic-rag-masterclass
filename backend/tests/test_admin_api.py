"""In-process checks of the admin settings request validation (no network, no Supabase)."""

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_db, require_admin
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[require_admin] = lambda: CurrentUser(id="u", email="a@b.c", jwt="j")
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "body",
    [
        {"embedding_dimensions": 768},
        {"llm_base_url": "http://example.com/v1"},
        {"llm_base_url": "ftp://localhost/v1"},
        {"embedding_base_url": "not a url"},
        {"llm_model": "has space"},
        {"embedding_model": ""},
        {"embedding_model": "x" * 201},
        {"llm_api_key": "short"},
        {"embedding_api_key": "has whitespace in it"},
    ],
)
@pytest.mark.parametrize("path,method", [("/api/admin/settings", "put"), ("/api/admin/settings/test", "post")])
def test_ADM_05_invalid_bodies_are_422(client, body, path, method):
    assert getattr(client, method)(path, json=body).status_code == 422


def test_ADM_05_url_validation_normalizes():
    from app.schemas import AdminSettingsIn

    ok = AdminSettingsIn(llm_base_url="https://x.test/v1/", embedding_base_url="http://localhost:11434/v1")
    assert ok.llm_base_url == "https://x.test/v1"
    assert ok.embedding_base_url == "http://localhost:11434/v1"
    assert AdminSettingsIn(llm_model=None).model_fields_set == {"llm_model"}


# --- ADM-08 embedding lock (in-process) ---


class _FakeQuery:
    def __init__(self, db):
        self.db = db

    def update(self, payload):
        self.db.updates.append(payload)
        return self

    def eq(self, *a):
        return self

    def execute(self):
        return type("R", (), {"data": [{"id": True}]})()


class _FakeDb:
    def __init__(self):
        self.updates = []
        self.rpcs = []

    def table(self, name):
        return _FakeQuery(self)

    def rpc(self, name, params):
        self.rpcs.append((name, params))
        return _FakeQuery(self)


@pytest.fixture
def lock_env(monkeypatch):
    from app.routers import admin as admin_router
    from app.services.app_settings import RuntimeConfig

    cfg = RuntimeConfig(
        llm_base_url="https://llm.test/v1",
        llm_api_key="k" * 20,
        llm_model="m/x",
        embedding_base_url="https://emb.test/v1",
        embedding_api_key="e" * 20,
        embedding_model="emb-small",
        embedding_dimensions=1536,
        sources={n: "env" for n in admin_router.TEXT_FIELDS + admin_router.KEY_FIELDS},
    )
    defaults = {
        "llm_base_url": cfg.llm_base_url,
        "llm_api_key": cfg.llm_api_key,
        "llm_model": cfg.llm_model,
        "embedding_base_url": cfg.embedding_base_url,
        "embedding_api_key": cfg.embedding_api_key,
        "embedding_model": cfg.embedding_model,
    }
    monkeypatch.setattr(admin_router, "get_runtime_config", lambda: cfg)
    monkeypatch.setattr(admin_router, "env_defaults", lambda: defaults)
    monkeypatch.setattr(admin_router, "invalidate", lambda: None)
    monkeypatch.setattr(admin_router, "count_chunks", lambda: 5)
    db = _FakeDb()
    app.dependency_overrides[require_admin] = lambda: CurrentUser(id="u", email="a@b.c", jwt="j")
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db, admin_router, monkeypatch
    app.dependency_overrides.clear()


def test_ADM_08_unit_changed_model_locked_writes_nothing(lock_env):
    client, db, _, _ = lock_env
    res = client.put("/api/admin/settings", json={"embedding_model": "emb-large", "llm_model": "a/b"})
    assert res.status_code == 409
    assert "5 chunks" in res.json()["detail"]
    assert db.updates == [] and db.rpcs == []


def test_ADM_08_unit_changed_base_url_locked(lock_env):
    client, db, _, _ = lock_env
    assert client.put("/api/admin/settings", json={"embedding_base_url": "https://other.test/v1"}).status_code == 409
    assert db.updates == []


def test_ADM_08_unit_zero_chunks_allows_change(lock_env):
    client, db, admin_router, mp = lock_env
    mp.setattr(admin_router, "count_chunks", lambda: 0)
    assert client.put("/api/admin/settings", json={"embedding_model": "emb-large"}).status_code == 200
    assert len(db.updates) == 1


def test_ADM_08_unit_same_value_and_null_default_allowed(lock_env):
    client, db, _, _ = lock_env
    assert client.put("/api/admin/settings", json={"embedding_model": "emb-small"}).status_code == 200
    assert client.put("/api/admin/settings", json={"embedding_model": None}).status_code == 200
    assert len(db.updates) == 2


def test_ADM_08_unit_key_change_allowed_while_locked(lock_env):
    client, db, _, _ = lock_env
    res = client.put("/api/admin/settings", json={"embedding_api_key": "n" * 20})
    assert res.status_code == 200
    assert db.rpcs and db.rpcs[0][0] == "set_app_secret"
