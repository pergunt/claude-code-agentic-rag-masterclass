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
