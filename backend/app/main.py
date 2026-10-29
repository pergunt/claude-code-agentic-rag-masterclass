import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, chat, documents, me, threads
from app.services import ingestion

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Background tasks die with the process, so anything still pending/processing is stuck.
    try:
        ingestion.fail_interrupted_documents()
    except Exception:
        logger.exception("Could not mark interrupted documents as failed")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Agentic RAG Masterclass API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(me.router)
    app.include_router(admin.router)
    app.include_router(threads.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    return app


app = create_app()
