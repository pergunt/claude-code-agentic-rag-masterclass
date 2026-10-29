from fastapi import APIRouter, Depends
from supabase import Client

from app.auth import CurrentUser, get_current_user, get_db, read_is_admin
from app.schemas import UserOut

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user), db: Client = Depends(get_db)) -> UserOut:
    return UserOut(id=user.id, email=user.email, is_admin=read_is_admin(db, user.id))
