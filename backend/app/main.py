from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, me, threads


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Agentic RAG Masterclass API")
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
    app.include_router(threads.router)
    app.include_router(chat.router)
    return app


app = create_app()
