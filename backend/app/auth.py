from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client
from supabase_auth.errors import AuthError

from app.db import create_anon_client, create_user_client

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str | None
    jwt: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    jwt = credentials.credentials
    try:
        response = create_anon_client().auth.get_user(jwt)
    except AuthError:
        response = None
    if response is None or response.user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return CurrentUser(id=response.user.id, email=response.user.email, jwt=jwt)


def get_db(user: CurrentUser = Depends(get_current_user)) -> Client:
    return create_user_client(user.jwt)


def read_is_admin(db: Client, user_id: str) -> bool:
    """Read the caller's own profiles row under RLS; a missing row means not an admin."""
    result = db.table("profiles").select("is_admin").eq("id", user_id).limit(1).execute()
    return bool(result.data and result.data[0].get("is_admin"))


def require_admin(
    user: CurrentUser = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> CurrentUser:
    if not read_is_admin(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
