import logging
from types import SimpleNamespace

import pytest

from app.services import app_settings

ENV = SimpleNamespace(
    llm_base_url="https://env-llm.test/v1",
    llm_api_key="env-llm-key-0000",
    llm_model="env/model",
    embedding_base_url="https://env-emb.test/v1",
    openai_api_key="env-emb-key-0000",
    embedding_model="env-emb",
    embedding_dimensions=1536,
)


class Query:
    def __init__(self, data):
        self.data = data

    def select(self, *a):
        return self

    def limit(self, n):
        return self

    def execute(self):
        return self


class FakeDB:
    def __init__(self, settings_row, secrets):
        self.settings_row, self.secrets = settings_row, secrets

    def table(self, name):
        assert name == "app_settings"
        return Query([self.settings_row] if self.settings_row else [])

    def rpc(self, name):
        assert name == "get_app_secrets"
        return Query(self.secrets)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(app_settings, "get_settings", lambda: ENV)
    app_settings.invalidate()
    yield
    app_settings.invalidate()


def test_ADM_09_env_fallback_when_service_client_fails(monkeypatch, caplog):
    def boom():
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set")

    monkeypatch.setattr(app_settings, "create_service_client", boom)
    with caplog.at_level(logging.WARNING):
        cfg = app_settings.get_runtime_config()
    assert cfg.llm_model == "env/model" and cfg.embedding_base_url == "https://env-emb.test/v1"
    assert cfg.llm_api_key == "env-llm-key-0000" and cfg.embedding_api_key == "env-emb-key-0000"
    assert set(cfg.sources.values()) == {"env"} and len(cfg.sources) == 6
    assert cfg.embedding_dimensions == 1536
    assert "env-llm-key-0000" not in caplog.text


def test_ADM_09_overrides_applied_with_app_sources_and_keys_hidden(monkeypatch):
    row = {"llm_model": "app/model", "llm_base_url": None, "embedding_model": "", "embedding_base_url": "https://app-emb.test/v1"}
    secrets = [{"name": "llm_api_key", "decrypted_secret": "app-secret-key-9999"}]
    monkeypatch.setattr(app_settings, "create_service_client", lambda: FakeDB(row, secrets))
    cfg = app_settings.get_runtime_config()
    assert cfg.llm_model == "app/model" and cfg.sources["llm_model"] == "app"
    assert cfg.llm_api_key == "app-secret-key-9999" and cfg.sources["llm_api_key"] == "app"
    assert cfg.embedding_base_url == "https://app-emb.test/v1" and cfg.sources["embedding_base_url"] == "app"
    # null / empty overrides and unset secrets stay on the env default
    assert cfg.llm_base_url == "https://env-llm.test/v1" and cfg.sources["llm_base_url"] == "env"
    assert cfg.embedding_model == "env-emb" and cfg.sources["embedding_model"] == "env"
    assert cfg.embedding_api_key == "env-emb-key-0000" and cfg.sources["embedding_api_key"] == "env"
    assert "app-secret-key-9999" not in repr(cfg) and "env-llm-key-0000" not in repr(cfg)


def test_ADM_09_cache_and_invalidate(monkeypatch):
    calls = []

    def make():
        calls.append(1)
        return FakeDB({"llm_model": f"m{len(calls)}"}, [])

    monkeypatch.setattr(app_settings, "create_service_client", make)
    assert app_settings.get_runtime_config().llm_model == "m1"
    assert app_settings.get_runtime_config().llm_model == "m1"  # cached
    app_settings.invalidate()
    assert app_settings.get_runtime_config().llm_model == "m2"
