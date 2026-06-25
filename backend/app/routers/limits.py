from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/limits", tags=["limits"])


@router.get("/")
async def list_limits(user: dict = Depends(get_current_user)):
    return []
