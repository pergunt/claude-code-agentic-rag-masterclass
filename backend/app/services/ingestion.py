"""Document ingestion: validate helpers plus the background pipeline (download, chunk, embed, store).

This is the only module that uses the service-role client. Request handlers stay on the user's JWT.
"""

import logging
import re
import time
from datetime import datetime, timezone

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from app.config import get_settings
from app.db import create_service_client
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts

logger = logging.getLogger(__name__)

BUCKET = "documents"
SUPPORTED_TYPES = {".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown"}
INTERRUPTED_MESSAGE = "Processing was interrupted by a server restart. Delete and upload again."
BATCH_SIZE = 100


class UnsupportedFile(ValueError):
    pass


def decode_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsupportedFile("File is not UTF-8 text") from exc
    if "\x00" in text:  # Postgres text columns reject NUL
        raise UnsupportedFile("File is not UTF-8 text")
    return text


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:100]
    return cleaned or "file"


def storage_path(user_id: str, doc_id: str, filename: str) -> str:
    return f"{user_id}/{doc_id}/{safe_filename(filename)}"


def ingestion_configured() -> str | None:
    """Return the reason ingestion can't run, or None when it can."""
    settings = get_settings()
    if not settings.supabase_service_role_key:
        return "Ingestion is not configured: SUPABASE_SERVICE_ROLE_KEY is not set"
    if not settings.openai_api_key:
        return "Ingestion is not configured: OPENAI_API_KEY is not set"
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dev_delay() -> None:
    delay = get_settings().ingestion_stage_delay_seconds
    if delay > 0:
        time.sleep(delay)


@traceable(name="ingest_document", run_type="chain")
def process_document(document_id: str) -> None:
    """Chunk and embed one uploaded document. Sync: FastAPI runs it in the threadpool."""
    settings = get_settings()
    db = create_service_client()
    rows = db.table("documents").select("*").eq("id", document_id).limit(1).execute().data
    if not rows:  # deleted before processing started
        return
    doc = rows[0]
    run = get_current_run_tree()
    if run is not None:
        run.metadata.update({"document_id": document_id, "user_id": doc["user_id"]})

    try:
        _dev_delay()
        db.table("documents").update({"status": "processing", "updated_at": _now()}).eq(
            "id", document_id
        ).execute()

        data = db.storage.from_(BUCKET).download(doc["storage_path"])
        chunks = chunk_text(decode_text(data), settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("No text content found")

        # Idempotent re-run: drop any earlier chunks first.
        db.table("chunks").delete().eq("document_id", document_id).execute()
        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_start : batch_start + BATCH_SIZE]
            vectors = embed_texts(batch)
            db.table("chunks").insert(
                [
                    {
                        "document_id": document_id,
                        "user_id": doc["user_id"],
                        "chunk_index": batch_start + i,
                        "content": content,
                        "embedding": vector,
                    }
                    for i, (content, vector) in enumerate(zip(batch, vectors))
                ]
            ).execute()

        _dev_delay()
        db.table("documents").update(
            {"status": "completed", "chunk_count": len(chunks), "error": None, "updated_at": _now()}
        ).eq("id", document_id).execute()
        if run is not None:
            run.metadata["chunk_count"] = len(chunks)
    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        try:
            db.table("chunks").delete().eq("document_id", document_id).execute()
            db.table("documents").update(
                {"status": "failed", "error": str(exc)[:1000], "chunk_count": 0, "updated_at": _now()}
            ).eq("id", document_id).execute()
        except Exception:
            logger.exception("Could not record failure for document %s", document_id)


def fail_interrupted_documents() -> None:
    """On startup, mark documents left pending/processing by a killed process as failed."""
    if not get_settings().supabase_service_role_key:
        logger.info("Skipping interrupted-document sweep: SUPABASE_SERVICE_ROLE_KEY is not set")
        return
    db = create_service_client()
    db.table("documents").update(
        {"status": "failed", "error": INTERRUPTED_MESSAGE, "updated_at": _now()}
    ).in_("status", ["pending", "processing"]).execute()
