from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("/")
async def get_group(user: dict = Depends(get_current_user)):
    return {}
