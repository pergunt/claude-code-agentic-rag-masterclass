from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.schemas import UserOut

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email)
