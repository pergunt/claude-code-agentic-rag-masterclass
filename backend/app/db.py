from fastapi import HTTPException, status
from supabase import Client, ClientOptions, create_client

from app.config import get_settings


def create_anon_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Supabase is not configured")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def create_user_client(jwt: str) -> Client:
    """Anon-key client that sends the user's JWT, so every query runs under RLS.

    The Authorization header is set in the client options so Storage runs as the user too;
    postgrest.auth() alone only covers PostgREST.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Supabase is not configured")
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(headers={"Authorization": f"Bearer {jwt}"}),
    )
    client.postgrest.auth(jwt)
    return client


def create_service_client() -> Client:
    """Service-role client that bypasses RLS: background ingestion only, never in request handlers.

    Always filter by id and set user_id explicitly.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
