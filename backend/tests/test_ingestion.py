from types import SimpleNamespace

import pytest

from app.services import ingestion


def test_ING_09_decode_strips_bom():
    assert ingestion.decode_text(b"\xef\xbb\xbfhi") == "hi"


def test_ING_09_decode_rejects_invalid_utf8():
    with pytest.raises(ingestion.UnsupportedFile):
        ingestion.decode_text(b"\xff\xfe\x00bad")


def test_ING_09_decode_rejects_nul_byte():
    with pytest.raises(ingestion.UnsupportedFile):
        ingestion.decode_text(b"ab\x00cd")


class FakeDB:
    def __init__(self):
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return self

    def update(self, payload):
        self.calls.append(("update", payload))
        return self

    def in_(self, col, values):
        self.calls.append(("in_", col, values))
        return self

    def execute(self):
        self.calls.append(("execute",))
        return self


def test_ING_07_sweep_marks_pending_processing_failed(monkeypatch):
    db = FakeDB()
    created = []
    monkeypatch.setattr(ingestion, "get_settings", lambda: SimpleNamespace(supabase_service_role_key="k"))
    monkeypatch.setattr(ingestion, "create_service_client", lambda: created.append(1) or db)
    ingestion.fail_interrupted_documents()
    assert created == [1]
    assert ("table", "documents") in db.calls
    payload = next(c[1] for c in db.calls if c[0] == "update")
    assert payload["status"] == "failed"
    assert payload["error"] == ingestion.INTERRUPTED_MESSAGE
    in_call = next(c for c in db.calls if c[0] == "in_")
    assert in_call[1] == "status"
    assert in_call[2] == ["pending", "processing"]
    assert ("execute",) in db.calls


def test_ING_07_sweep_skipped_without_service_key(monkeypatch):
    created = []
    monkeypatch.setattr(ingestion, "get_settings", lambda: SimpleNamespace(supabase_service_role_key=""))
    monkeypatch.setattr(ingestion, "create_service_client", lambda: created.append(1))
    ingestion.fail_interrupted_documents()
    assert created == []
