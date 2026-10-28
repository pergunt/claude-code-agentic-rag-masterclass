from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import get_settings


def create_anon_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Supabase is not configured")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def create_user_client(jwt: str) -> Client:
    """Anon-key client that sends the user's JWT, so every query runs under RLS."""
    client = create_anon_client()
    client.postgrest.auth(jwt)
    return client
