import logging
import posixpath
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from supabase import Client

from app.auth import CurrentUser, get_current_user, get_db
from app.config import get_settings
from app.schemas import DocumentOut
from app.services import ingestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def fetch_document(db: Client, document_id: str) -> dict:
    """Return the document row, or 404. RLS hides other users' documents."""
    rows = db.table("documents").select("*").eq("id", document_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return rows[0]


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Client = Depends(get_db)) -> list[dict]:
    return db.table("documents").select("*").order("created_at", desc=True).execute().data


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Client = Depends(get_db)) -> dict:
    return fetch_document(db, document_id)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    problem = ingestion.ingestion_configured()
    if problem:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, problem)

    filename = file.filename or "file"
    extension = posixpath.splitext(filename)[1].lower()
    mime_type = ingestion.SUPPORTED_TYPES.get(extension)
    if mime_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Use one of: {', '.join(ingestion.SUPPORTED_TYPES)}",
        )

    max_bytes = get_settings().max_upload_bytes
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File is larger than {max_bytes // (1024 * 1024)} MiB"
        )
    try:
        text = ingestion.decode_text(data)
    except ingestion.UnsupportedFile as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    if not text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")

    doc_id = uuid4()
    path = ingestion.storage_path(user.id, str(doc_id), filename)
    # Storage first, so a failed upload never shows a phantom row through Realtime.
    try:
        db.storage.from_(ingestion.BUCKET).upload(path, data, file_options={"content-type": mime_type})
    except Exception as exc:
        logger.exception("Storage upload failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not store the file") from exc

    try:
        row = (
            db.table("documents")
            .insert(
                {
                    "id": str(doc_id),
                    "filename": filename,
                    "storage_path": path,
                    "mime_type": mime_type,
                    "size_bytes": len(data),
                }
            )
            .execute()
            .data[0]
        )
    except Exception:
        try:
            db.storage.from_(ingestion.BUCKET).remove([path])
        except Exception:
            logger.exception("Could not remove orphaned storage object %s", path)
        raise

    background_tasks.add_task(ingestion.process_document, str(doc_id))
    return row


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Client = Depends(get_db)) -> Response:
    doc = fetch_document(db, document_id)
    try:
        db.storage.from_(ingestion.BUCKET).remove([doc["storage_path"]])
    except Exception:
        logger.exception("Could not remove storage object %s", doc["storage_path"])
    db.table("documents").delete().eq("id", document_id).execute()  # chunks cascade
    return Response(status_code=status.HTTP_204_NO_CONTENT)
