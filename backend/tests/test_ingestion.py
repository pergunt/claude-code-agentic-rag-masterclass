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


class DocDB:
    """Minimal supabase stand-in for process_document: records documents.update payloads."""

    def __init__(self):
        self.doc_updates = []
        self.storage = self
        self._table = None
        self._payload = None

    def from_(self, _bucket):
        return self

    def download(self, _path):
        return b"hello world"

    def table(self, name):
        self._table, self._payload, self._mode = name, None, "select"
        return self

    def select(self, *_):
        return self

    def update(self, payload):
        self._mode, self._payload = "update", payload
        return self

    def insert(self, _rows):
        self._mode = "insert"
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def eq(self, *_):
        return self

    def limit(self, _n):
        return self

    def execute(self):
        if self._mode == "update" and self._table == "documents":
            self.doc_updates.append(self._payload)
        if self._mode == "select":
            self.data = [{"id": "d1", "user_id": "u1", "storage_path": "u1/d1/x.md"}]
        return self


def test_ADM_08_process_document_records_embedding_model(monkeypatch):
    db = DocDB()
    cfg = SimpleNamespace(embedding_model="text-embedding-3-large")
    monkeypatch.setattr(ingestion, "get_settings", lambda: SimpleNamespace(chunk_size=500, chunk_overlap=50))
    monkeypatch.setattr(ingestion, "get_runtime_config", lambda: cfg)
    monkeypatch.setattr(ingestion, "create_service_client", lambda: db)
    monkeypatch.setattr(ingestion, "embed_texts", lambda texts, c: [[0.0] for _ in texts])
    monkeypatch.setattr(ingestion, "_dev_delay", lambda: None)
    ingestion.process_document("d1")
    final = db.doc_updates[-1]
    assert final["status"] == "completed"
    assert final["embedding_model"] == "text-embedding-3-large"
